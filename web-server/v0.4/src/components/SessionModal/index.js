import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'dva';
import { Modal, Form, Input, Button, message, Tooltip, Icon } from 'antd';
import styles from './index.less';

const { TextArea } = Input;

@connect(({ global, loading }) => ({
  datastoreConfig: global.datastoreConfig,
  loadingConfig: loading.effects['global/saveSharedConfig'],
}))
class SessionModal extends Component {
  static propTypes = {
    configData: PropTypes.object.isRequired,
  };

  constructor(props) {
    super(props);

    this.state = {
      description: '',
      visible: false,
      confirmLoading: false,
      generatedLink: '',
    };
  }

  componentDidMount() {
    const { dispatch } = this.props;
    dispatch({
      type: 'global/fetchDatastoreConfig',
    });
  }

  componentWillReceiveProps() {
    const { loadingConfig } = this.props;
    this.setState({
      confirmLoading: loadingConfig,
    });
  }

  showSuccess = () => {
    const { generatedLink } = this.state;

    Modal.success({
      title: 'Generated session link',
      content: (
        <div style={{ display: 'flex', flex: 1, flexDirection: 'row' }}>
          <Input id="generatedUrl" value={generatedLink} />
          <Button style={{ marginLeft: 8 }} icon="copy" onClick={this.copyLink}>
            Copy Link
          </Button>
        </div>
      ),
    });
  };

  handleCancel = () => {
    this.setState({
      visible: false,
    });
  };

  showModal = () => {
    this.setState({
      visible: true,
    });
  };

  onGenerate = () => {
    const { configData, dispatch, datastoreConfig } = this.props;
    const { description } = this.state;
    const stringProp = JSON.stringify(configData);
    dispatch({
      type: 'global/saveSharedConfig',
      payload: {
        stringProp,
        description,
        datastoreConfig,
      },
    }).then(result => {
      setTimeout(() => {
        this.setState({
          visible: false,
          confirmLoading: false,
          generatedLink: `${window.location.origin}/dashboard/share/${result.data.createUrl.id}`,
        });
        this.showSuccess();
      }, 2000);
    });
  };

  copyLink = () => {
    const generatedUrl = document.getElementById('generatedUrl');
    generatedUrl.select();
    document.execCommand('copy');
    message.success(`Copied the link: ${generatedUrl.value}`);
  };

  changeDescp = e => {
    this.setState({
      description: e.target.value,
    });
  };

  render() {
    const { visible, confirmLoading, description } = this.state;
    return (
      <span>
        <Tooltip title="Share" onClick={this.showModal}>
          <a className={styles.action}>
            <Icon type="share-alt" />
          </a>
        </Tooltip>
        <Modal
          title="Share Session Link"
          visible={visible}
          confirmLoading={confirmLoading}
          onOk={this.onGenerate}
          onCancel={this.handleCancel}
          footer={[
            <Button key="back" onClick={this.handleCancel}>
              Cancel
            </Button>,
            <Button key="submit" type="primary" onClick={this.onGenerate} loading={confirmLoading}>
              Save
            </Button>,
          ]}
        >
          <Form layout="vertical">
            <Form.Item label="Description">
              <TextArea
                rows={2}
                id="description"
                placeholder={description}
                onChange={this.changeDescp}
              />
            </Form.Item>
          </Form>
        </Modal>
      </span>
    );
  }
}

export default SessionModal;
