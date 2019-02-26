## Foreword


Pbench Dashboard is a web-based platform for consuming indexed performance benchmark data. The platform provides a consolidated view of benchmark data within tables, charts, and other powerful visualizations. Users are able to quickly navigate through benchmark data and tune analytics through comparison tools for in-depth analysis.

## Scaffolding

```bash
├── public
│   └── favicon.ico                 # favicon
├── mock
│   └── datastoreConfig.js.example  # datastore configuration
├── config
│   ├── config.js                   # webpack configuration
│   └── router.config.js            # webpack routing configuration
├── src
│   ├── assets                      # local static files
│   ├── common                      # common configurations (navigation, menu, etc.)
│   ├── components                  # component definitions
│   ├── e2e                         # integrated test cases
│   ├── layouts                     # common layouts
│   ├── models                      # redux models
│   ├── routes                      # app pages and templates
│   ├── services                    # redux services
│   ├── utils                       # utility scripts
│   ├── theme.js                    # app theme configuration
│   ├── index.ejs                   # HTML entry
│   ├── index.js                    # app entry
│   ├── index.less                  # global stylesheet
│   └── router.js                   # router entry file
├── .eslintrc.js                    # js linting configuration
├── .gitignore
├── .prettierignore                 # code formatting ignore file
├── .prettierrc                     # code formatting configuration
├── .stylelintrc                    # style linting configuration
├── jsconfig.json                   # js compiler configuration
├── config.json.j2                  # template JSON configuration
├── package.json                    # project dependencies
├── README.md
└── LICENSE.ant-design-pro          # template license file
```

## Assets

Assets placed in the `public` directory are copied to the `dist` directory for reference in the generated `index.html` file during the build process.

Assets placed in the `src/assets/` directory are only referenced within component or layout definitions and are packaged in the generated `***.js` file during the build process.


## Installation

Install Dependencies

`yarn` is the default dependency manager used for installing and building the application.

```bash
$ yarn install
```

Start Development Server

```bash
$ yarn start
```

This will automatically open the application on [http://localhost:8000](http://localhost:8000).

## Local Development

Both the production and development builds of the dashboard require specific configurations in order to run on their respective environment.

Copy the `datastoreConfig.js.example` file in the `mock/` directory to `datastoreConfig.js` and modify the configuration fields within the route definition. Please reference the following example for required configuration fields.

```JavaScript
export default {
  '/dev/datastoreConfig': {
      "elasticsearch": "http://elasticsearch.example.com",
      "results": "http://results.example.com",
      "prefix": "example.prefix",
      "run_index": "example.index"
  },
}
```

## Build

Build Application

```bash
$ yarn build
```

This will generate the `dist` folder in the root directory, which contains packaged files such as `***.js`, `***.css`, and `index.html`.


## Template

This application is based on v1 of Ant Design Pro which is a production-ready UI solution for admin interfaces. For more information regarding the foundation and template of the application, please visit [https://v1.pro.ant.design/docs/getting-started](https://v1.pro.ant.design/docs/getting-started).

For information regarding the library license, please reference the `LICENSE.ant-design-pro` file.
