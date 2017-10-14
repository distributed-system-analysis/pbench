# exit-code

`process.exitCode` behavior back-ported from io.js and Node.js 0.12+

## USAGE

```javascript
require('exit-code')

process.exitCode = 2

// do some other stuff
// when the process exits, it'll do it with a code of 2
```
