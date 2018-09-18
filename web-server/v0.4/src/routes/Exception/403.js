import { Link } from 'dva/router';
import Exception from 'ant-design-pro/lib/Exception';

export default () => (
  <Exception type="403" desc={"Sorry, you don't have access to this page."} style={{ minHeight: 500, height: '80%' }} linkElement={Link} />
);
