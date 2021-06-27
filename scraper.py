from pathlib import Path

import holoviews as hv
import hvplot.pandas  # noqa
import numpy as np
import pandas as pd
from holoviews.operation import histogram
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

salary_db_url = "https://www.cusys.edu/budget/cusalaries/"
salaries_pkl = "salaries.pkl"


def scrape_salaries():
    browser = webdriver.Chrome()
    browser.implicitly_wait(
        10
    )  # Wait up to 10 seconds for element to load when finding
    browser.get(salary_db_url)

    # Select Boulder campus and search
    browser.find_element_by_xpath(
        r'//select[@name="Value1_1"]/option[@value="Boulder"]'
    ).click()
    browser.find_element_by_xpath(r'//input[@name="searchID"]').click()

    dfs = []
    while True:
        table = browser.find_element_by_xpath(
            r'//table[contains(@class, "cbResultSetTable")]'
        )
        dfs.extend(pd.read_html(table.get_attribute("outerHTML")))

        try:
            next_button = browser.find_element_by_xpath(
                r'//a[@data-cb-name="JumpToNext"]'
            )
        except NoSuchElementException:
            break

        # Click next page
        next_button.click()

        # Wait for new page to load (signalled by stale `next_button`)
        WebDriverWait(browser, 10).until(expected_conditions.staleness_of(next_button))

    browser.quit()

    print(f"Scraped {len(dfs)} pages")
    df = pd.concat(dfs)

    # Munging
    df["TOTAL FUNDING"] = (
        df["TOTAL FUNDING"].replace(r"[\$,]", "", regex=True).astype(float)
    )

    return df


def load_salaries(filepath="salaries.pkl"):
    filepath = Path(filepath)
    if filepath.exists():
        df = pd.read_pickle(filepath)
    else:
        df = scrape_salaries()

    return df


def filter_uni_ft_pra(df):
    mask = df["JOB TITLE"] == "Professional Research Asst"
    mask &= df["JOB FULL TIME PCNT"] == 100.0

    return df[mask]


def filter_cires_ft_pra(df):
    df = filter_uni_ft_pra(df)
    mask = df["SCHOOL/COLLEGE/FUNCTION"] == "Coop Inst Res/Envrm Sci - Dir"

    return df[mask]


def plot_distribution(df, salary=None):
    mini, lower, median, upper, maxi = df["TOTAL FUNDING"].quantile(
        [0, 0.25, 0.5, 0.75, 1]
    )

    xticks = np.arange(mini + (10000 - mini % 10000), maxi // 10000 * 10000, 10000)
    # xticks = np.insert(xticks, 0, [lower, median, upper, salary])

    kde_plot = df.hvplot.kde("TOTAL FUNDING").opts(
        xticks=xticks, yticks=[0], xrotation=45, xformatter="%d"
    )
    lower_line = hv.VLine(lower).opts(line_dash="dashed", color="black")
    upper_line = hv.VLine(upper, label="IQR").opts(line_dash="dashed", color="black")
    median_line = hv.VLine(median, label="median").opts(
        line_dash="dashed", color="blue"
    )

    quantiles = (lower_line * median_line * upper_line).opts(
        hv.opts.VLine(line_width=1)
    )

    pdf_plot = kde_plot * quantiles

    if salary is not None:
        pdf_plot *= hv.VLine(salary, label="salary").opts(line_width=1, color="red")

    return pdf_plot
