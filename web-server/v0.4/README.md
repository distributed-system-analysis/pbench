## Foreword

Pbench Dashboard is a web-based platform for consuming indexed performance benchmark data. The platform provides a consolidated view of benchmark data within tables, charts, and other powerful visualizations. Users are able to quickly navigate through benchmark data and tune analytics through comparison tools for in-depth analysis.

## Scaffolding

```bash
├── public
│   └── favicon.ico          # favicon
├── src
│   ├── assets               # local static files
│   ├── common               # common configurations (navigation, menu, etc.)
│   ├── components           # component definitions
│   ├── e2e                  # integrated test cases
│   ├── layouts              # common layouts
│   ├── models               # redux models
│   ├── routes               # app pages and templates
│   ├── services             # redux services
│   ├── utils                # utility scripts
│   ├── theme.js             # app theme configuration
│   ├── index.ejs            # HTML entry
│   ├── index.js             # app entry
│   ├── index.less           # global stylesheet
│   └── router.js            # router entry file
├── .babelrc.js              # js compiler configuration
├── .eslintrc.js             # js linting configuration
├── .gitignore               
├── .prettierignore          # code formatting ignore file
├── .prettierrc              # code formatting configuration
├── .stylelintrc             # style linting configuration
├── .webpackrc.js            # module bundler configuration
├── jsconfig.json            # js compiler configuration
├── config.json.j2           # template JSON configuration
├── package.json             # project dependencies
├── README.md               
└── LICENSE.ant-design-pro   # template license file
```

## Assets

Assets placed in the `public` directory are copied to the `dist` directory for reference in the generated `index.html` file during the build process.

Assets placed in the `src/assets/` directory are only referenced within components or layouts definitions and is packaged in the generated `***.js` file during the build process.


## Installation

Install Dependencies

```bash
$ npm install
```

Start Development Server

```bash
$ npm start
```

This will automatically open the application on [http://localhost:8000](http://localhost:8000).

## Local Development

Both the production and development builds of the dashboard require specific configurations in order to run on their respective environment. For local development, modify the following configuration definitions:

`.webpackrc.js`

```Javascript
publicPath: '/'
```

Create and include a JSON config file in the root directory. Please reference the following example for required configuration fields.

`dev.config.json`

```JSON
{
   "elasticsearch": "http://elasticsearch.example.com",
   "results": "http://results.example.com",
   "prefix": "example.prefix",
   "run_index": "example.index"
}
```

For local development, reference `dev.config.json` on localhost through the `global` service.

`/src/services/global.js`

```Javascript
export async function queryDatastoreConfig() {
  return request('http://localhost:8000/dev.config.json', {
    method: 'GET',
  });
}
```

## Build

Build Application

```bash
$ npm run build
```

This will generate the `dist` folder in the root directory, which contains packaged files such as `***.js`, `***.css`, and `index.html`.


## Template 

This application is based on v1 of Ant Design Pro which is a production-ready UI solution for admin interfaces. For more information regarding the foundation and template of the application, please visit [https://v1.pro.ant.design/docs/getting-started](https://v1.pro.ant.design/docs/getting-started).

For information regarding the library license, please reference the `LICENSE.ant-design-pro` file. 
