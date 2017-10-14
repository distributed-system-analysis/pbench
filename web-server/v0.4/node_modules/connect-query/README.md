# connect-query

Parse query parameters in Connect or Express

[![NPM version](https://badge.fury.io/js/connect-query.png)](http://badge.fury.io/js/connect-query)

## Install

```
npm install connect-query --save
```

## Usage

```js
var connect = require('connect');
var query = require('connect-query');
var app = connect();

app.use(query());

app.listen(300);
```

## Run tests

```
npm install
npm test
```
