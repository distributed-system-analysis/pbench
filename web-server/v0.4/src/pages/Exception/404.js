import { Link } from 'dva/router';
import Exception from 'ant-design-pro/lib/Exception';

export default () => (
  <Exception type="404" desc={"Sorry, the page you visited does not exist."} style={{ minHeight: 500, height: '80%' }} linkElement={Link} />
);
