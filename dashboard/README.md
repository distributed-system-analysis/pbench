# Pbench Dashboard

Pbench Dashboard is a web-based platform for consuming indexed performance benchmark data. The platform provides a consolidated view of benchmark data within tables, charts, and other powerful visualizations. Users are able to quickly navigate through benchmark data and tune analytics through comparison tools for in-depth analysis.

## Dashboard directory structure

### [`public`](public/)

Contains the root application `index.html` and React template artifacts.

### [`server`](server/)

The source for an NPM express server that's used in local developer mode to reflect
the server `/api/v1/endpoints` API call to a remote server. This enables local
debugging against a real Pbench Server.

### [`src`](src/)

The Pbench Dashboard Javascript source plus additional CSS/LESS and artifacts.

#### [`src/assets`](src/assets/)

Assets placed in the `src/assets/images` directory are only referenced within component or layout definitions and are packaged in the generated `***.js` file during the build process.

#### [`src/modules`](src/modules/)

`modules` directory has all containers (patent layouts) and components (react components). 

#### [`src/utils`](src/utils/)

The `utils` directory has all helper/utility scripts.

## Setup

1. Install NodeJS - [offical setup guide](https://nodejs.org/en/download/package-manager/)

2. Clone the [Pbench repo](https://github.com/distributed-system-analysis/pbench)

3. Install all the npm packages.
Navigate to `dashboard` directory and run following command 
	```bash
	$ npm install
	```

## Development and Test 

Create a `.env` file in the root directory (`/dashboard/`) and declare the environment variable `PBENCH_SERVER`.
This `PBENCH_SERVER` environment variable is the base URL for all API calls and it should point to a real pbench server.
	```bash
	PBENCH_SERVER=<pbench server url>
	```

In order to start the development express server and run the application use the following command 
	```bash
	$ npm run dev
	```
	> Note: The application runs on http://localhost:3000.

## Build

To build the application run the following command

```bash
$ npm run build
```
This will generate the `build` folder in the root directory, which contains packaged files such as `***.js`, `***.css`, and `index.html`.

Then, copy the `build` folder to the proper place on the server for deployment.

## Local and Production builds

Both the production and development builds of the dashboard require API endpoint configurations in order to query data from specific datastores.

In the production environment, the dashboard code is loaded directly from the Pbench Server and is able to get the endpoint definitions implicitly from that host. 

When running locally, the express passthrough server uses the environment variable to get the endpoints from a remote server.

## Storage
Pbench Dashboard stores data using local browser storage and cookies.

## Template
This application is based on v4 of PatternFly which is a production-ready UI solution for admin interfaces. For more information regarding the foundation and template of the application, please visit [PatternFly](https://www.patternfly.org/v4/get-started/design)

## Resources

- [create-react-app](https://github.com/facebook/create-react-app)   

- [ReactJS](https://reactjs.org/) 

- [React-Redux](https://github.com/reduxjs/react-redux)