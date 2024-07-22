[WTRobot](https://pypi.org/project/wtrobot/) is a keyword driven UI/frontend testing framework.

## Setup

### Install

```console

> pip install wtrobot

```

> NOTE

- Selenium_drivers folders have your selenium webdrivers geckodrivers(for firefox) and chromedrivers(for chrome and chromium)

- If script fails due to drivers issue, you need to find appropriate selenium webdriver according to your browser version

  - [firefox](https://github.com/mozilla/geckodriver/releases) & [chrome/chromium](https://chromedriver.chromium.org/downloads)

- Unzip or untar the executable and place in selenium_drivers dir.

## Executing Script

- Write all your test cases into test.yaml and execute

```console

> wtrobot

```

> NOTE

- If config(in `config.json`) is missing on initial run, tool will ask you for few configuration question and create `config.json` file.
- Make sure files which you mention as config(in `config.json`) should exist else will exit with error.

## Syntax of test.yaml file

- Write your WTRobot test cases in `test.yaml` files
  
```

sequence:

- testcase 1

- testcase 2 ...

test:

- testcase 1:

- scenario: <your test senario desc>

- step 1:

name: <your step desc>

action: goto | click | input | hover | scroll ...

target: text | xpath | css path

value: <data>

- step 2:

...

- testcase 2:

...

```

[sample example](examples/test.yaml)

[detailed syntax](examples/syntax_docs.rst)

- Scenario and name are just detailed text description about your test case scenario and steps, they are useful for detailed logging

- There are only four important section to be considered while writing this script file

  - `action`: what to perform (e.g. click, input and etc)

  - `target`: on what to perform (e.g. Text widget on web page, xpath of widget and etc)

  - `value`: with what data (e.g. if an input field then what value to input)
  
  - `assert`: after performing some action, what you want to validate.	  
    
    - It can be text, element, url   
