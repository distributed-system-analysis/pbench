import 'rc-drawer/assets/index.css';
import ReactJS from 'react';
import DrawerMenu from 'rc-drawer/lib';
import SiderMenu from '@/components/SiderMenu/SiderMenu';

const SiderMenuWrapper = props => {
  const { isMobile, collapsed } = props;
  return isMobile ? (
    <DrawerMenu
      getContainer={null}
      level={null}
      handleChild={<i className="drawer-handle-icon" />}
      onHandleClick={() => {
        props.onCollapse(!collapsed);
      }}
      open={!collapsed}
      onMaskClick={() => {
        props.onCollapse(true);
      }}
    >
      <SiderMenu {...props} collapsed={isMobile ? false : collapsed} />
    </DrawerMenu>
  ) : (
    <SiderMenu {...props} />
  );
};

export default SiderMenuWrapper;
