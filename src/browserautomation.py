import logging
from selenium import webdriver
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from utils.config import SELENIUM_URL, BROWSERLESS_URL


logger = logging.getLogger(__name__)


def test_selenium():
    logger.info("Starting Selenium test with SELENIUM_URL: %s", SELENIUM_URL)
    logger.info("Selenium step: preparing remote driver connection")

    driver = None
    try:
        driver = webdriver.Remote(
            command_executor=SELENIUM_URL,
            options=webdriver.ChromeOptions(),
        )
        logger.info("Selenium step: remote driver connection established")

        logger.info("Session acquired: %s", driver.session_id)
        logger.info("Selenium step: navigating to target page")

        driver.get("https://example.com")
        logger.info("Selenium step: page navigation completed")
        logger.info("Title: %s", driver.title)
        logger.info("Selenium step: title retrieval completed")
        logger.info("Selenium test completed for session")
    finally:
        if driver is not None:
            logger.info("Selenium step: closing remote driver")
            driver.quit()
            logger.info("Selenium step: remote driver closed")


def test_playwright_browserless():
    logger.info("Starting Playwright Browserless test with BROWSERLESS_URL: %s", BROWSERLESS_URL)
    logger.info("Playwright step: creating Playwright context manager")

    with sync_playwright() as p:
        logger.info("Playwright step: Playwright context manager entered")
        browser = None
        context = None
        try:
            logger.info("Playwright step: connecting to remote browser")
            browser = p.chromium.connect_over_cdp(BROWSERLESS_URL)
            logger.info("Playwright step: remote browser connection established")
            logger.info("Playwright step: creating browser context")
            context = browser.new_context()
            logger.info("Playwright step: browser context created")
            logger.info("Playwright step: creating new page")
            page = context.new_page()
            logger.info("Playwright step: new page created")
            logger.info("Playwright step: navigating to target page")
            page.goto("https://example.com", wait_until="domcontentloaded", timeout=30000)
            logger.info("Playwright step: page navigation completed")
            logger.info("Title: %s", page.title())
            logger.info("Playwright step: title retrieval completed")
            logger.info("Playwright Browserless test completed for session")
        except PlaywrightError:
            logger.exception("Playwright Browserless test failed")
            raise
        finally:
            if context is not None:
                logger.info("Playwright step: closing browser context")
                context.close()
                logger.info("Playwright step: browser context closed")
            if browser is not None:
                logger.info("Playwright step: closing browser")
                browser.close()
                logger.info("Playwright step: browser closed")
