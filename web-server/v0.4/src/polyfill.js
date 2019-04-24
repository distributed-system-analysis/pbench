import 'url-polyfill';
import setprototypeof from 'setprototypeof';

// ReactJS depends on set/map/requestAnimationFrame
// https://reactjs.org/docs/javascript-environment-requirements.html
// import 'core-js/es6/set';
// import 'core-js/es6/map';
// import 'raf/polyfill'; 

// https://github.com/umijs/umi/issues/413
Object.setPrototypeOf = setprototypeof;
