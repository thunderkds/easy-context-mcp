import { render } from './view';
import './setup.js';
const api = require('./api');
import axios from 'axios';
import nothing from './missing';

export function start() {
  return render(api.load());
}
