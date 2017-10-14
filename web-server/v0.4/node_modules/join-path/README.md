# join-path

Join urls or system paths, even with undefined values.

## Install

```
npm install join-path --save
```

## Usage

```js
var join = require('join-path');

// OUTPUTS: some/path/for/testing
join('some', 'path', '/for/', undefined, '/testing'); 

// OUTPUTS: http://test.com/aboutus/projects
join('http://test.com', '/aboutus', 'projects');
```

## Run Tests

```
npm install
npm test
```