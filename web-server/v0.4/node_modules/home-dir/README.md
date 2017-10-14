# home-dir

Get home directory path on any platform

## Install

```
npm install home-dir --save
```

## Usage

```javascript
var homeDir = require('home-dir');

console.log(homeDir()); // Outputs full path to your home directory

// OR

var dir = homeDir('/path/to/somehwere');
console.log(dir) // OUTPUTS: /(HOME)/path/to/somewhere

// OR

var homeDir = require('home-dir').directory;
```