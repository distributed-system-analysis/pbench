import ReactJS from 'react';
import { Card } from 'antd';
import classNames from 'classnames';

import styles from './index.less';

const renderTotal = total => {
  let totalDom;
  switch (typeof total) {
    case 'undefined':
      totalDom = null;
      break;
    case 'function':
      totalDom = <div className={styles.total}>{total()}</div>;
      break;
    default:
      totalDom = <div className={styles.total}>{total}</div>;
  }
  return totalDom;
};

const ChartCard = ({
  loading = false,
  contentHeight,
  title,
  avatar,
  action,
  total,
  footer,
  children,
  ...rest
}) => {
  const content = (
    <div className={styles.chartCard}>
      <div
        className={classNames(styles.chartTop, {
          [styles.chartTopMargin]: !children && !footer,
        })}
      >
        <div className={styles.avatar}>{avatar}</div>
        <div className={styles.metaWrap}>
          <div className={styles.meta}>
            <span className={styles.title}>{title}</span>
            <span className={styles.action}>{action}</span>
          </div>
          {renderTotal(total)}
        </div>
      </div>
      {children && (
        <div className={styles.content} style={{ height: contentHeight || 'auto' }}>
          <div className={contentHeight && styles.contentFixed}>{children}</div>
        </div>
      )}
      {footer && (
        <div
          className={classNames(styles.footer, {
            [styles.footerMargin]: !children,
          })}
        >
          {footer}
        </div>
      )}
    </div>
  );

  return (
    <Card loading={loading} bodyStyle={{ padding: '20px 24px 8px 24px' }} {...rest}>
      {content}
    </Card>
  );
};

export default ChartCard;
