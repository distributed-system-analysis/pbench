import axios from 'axios';
import { LOCAL_BASE_URL } from './apiConstants';

export default axios.create({
  baseURL: LOCAL_BASE_URL,
  responseType: "json",
});