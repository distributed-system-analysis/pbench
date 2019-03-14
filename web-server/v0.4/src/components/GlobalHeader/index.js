import { PureComponent } from 'react';
import { routerRedux } from 'dva/router';
import { Icon, Divider, Tooltip } from 'antd';
import Debounce from 'lodash-decorators/debounce';
import { connect } from 'dva';
import styles from './index.less';
import SessionModal from '../SessionModal';

@connect(store => ({
  store,
}))
class GlobalHeader extends PureComponent {
  state = {
    visible: false,
    url: 'Click on generate to get URL',
    description: 'Add description here',
  };

  componentWillUnmount() {
    this.triggerResizeEvent.cancel();
  }

  toggle = () => {
    const { collapsed, onCollapse } = this.props;
    onCollapse(!collapsed);
    this.triggerResizeEvent();
  };

  /* eslint-disable*/
  @Debounce(600)
  triggerResizeEvent() {
    const event = document.createEvent('HTMLEvents');
    event.initEvent('resize', true, false);
    window.dispatchEvent(event);
  }

  showModal = () => {
    this.setState({
      visible: true,
    });
  };

  handleOk = e => {
    this.setState({
      visible: false,
    });
  };

  handleCancel = e => {
    this.setState({
      visible: false,
    });
  };

  onGenerate = () => {
    this.setState(
      {
        description: document.getElementById('description').value,
      },
      () => {
        const stringProp = JSON.stringify(this.props.store);
        console.log('generateed');
        axios({
          url: 'http://localhost:4466/',
          method: 'post',
          data: {
            query: `
            mutation($config: String!$description: String!) {
              createUrl(data: {config: $config,description: $description}) {
                id
                config
                description
              }
            }       
          `,
            variables: {
              config: stringProp,
              description: this.state.description,
            },
          },
        })
          .then(result => {
            this.setState({
              url: 'http://localhost:8000/dashboard/share/' + result.data.data.createUrl.id,
            });
          })
          .catch(err => {
            console.log(err);
          });
      }
    );
  };

  copyURL = () => {
    var copyText = document.getElementById('url');
    copyText.select();
    document.execCommand('copy');
    message.success('Copied the text: ' + copyText.value);
  };

  render() {
    const { collapsed, isMobile, logo, dispatch } = this.props;

    return (
      <div className={styles.header}>
        <div style={{ display: 'flex', flexDirection: 'row' }}>
          {isMobile && [
            <Link to="/" className={styles.logo} key="logo">
              <img src={logo} alt="logo" width="32" />
            </Link>,
            <Divider type="vertical" key="line" />,
          ]}
          <Icon
            className={styles.trigger}
            type={collapsed ? 'menu-unfold' : 'menu-fold'}
            onClick={this.toggle}
          />
        </div>
        <div className={styles.right}>
          <SessionModal configData={this.props.store} dispatch={dispatch} />
          <Tooltip
            title="Search"
            onClick={() => {
              dispatch(
                routerRedux.push({
                  pathname: '/search',
                })
              );
            }}
          >
            <a className={styles.action}>
              <Icon type="search" />
            </a>
          </Tooltip>
          <Tooltip title="Help">
            <a
              target="_blank"
              href="https://docs.google.com/document/d/1W4-vUpMzClBxQmwODDG4WLENmHXrL-adf-5GOF-NYg8/edit"
              rel="noopener noreferrer"
              className={styles.action}
            >
              <Icon type="question-circle-o" />
            </a>
          </Tooltip>
        </div>
        <Modal
          title="Share with others"
          visible={this.state.visible}
          onOk={this.handleOk}
          onCancel={this.handleCancel}
        >
          <Card type="inner">
            <Form>
              <Form.Item label="Generated URL">
                <Form>
                  <Form.Item>
                    <Input id="url" value={this.state.url} />
                    <Input.TextArea
                      id="description"
                      rows={4}
                      placeholder={this.state.description}
                    />
                    <Button
                      type="primary"
                      shape="circle-outline"
                      icon="copy"
                      size="default"
                      style={{ float: 'right' }}
                      onClick={this.copyURL}
                    />
                    <Button type="primary" onClick={this.onGenerate}>
                      Generate
                    </Button>
                  </Form.Item>
                </Form>
              </Form.Item>
            </Form>
          </Card>
        </Modal>
      </div>
    );
  }
}

export default GlobalHeader;
