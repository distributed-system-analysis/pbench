import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Modal, Form, Input, Button, message, Tooltip, Icon } from 'antd';
import axios from 'axios';

const { TextArea } = Input;

export default class ShareModal extends Component {
  static propTypes = {
    configData: PropTypes.object.isRequired,
    styles: PropTypes.object.isRequired,
  };

  constructor(props) {
    super(props);

    this.state = {
      description: 'Add description here.',
      visible: false,
      confirmLoading: false,
      generatedLink: 'http://samplelink.com',
    };
  }

  showSucces = () => {
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
    const { configData } = this.props;
    const { description } = this.state;
    const stringProp = JSON.stringify(configData);
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
          description,
        },
      },
    }).then(result => {
      this.setState({
        confirmLoading: true,
      });
      if (document.getElementById('description')) {
        setTimeout(() => {
          this.setState({
            visible: false,
            confirmLoading: false,
            description: document.getElementById('description').value,
            generatedLink: `http://localhost:8000/dashboard/share/${result.data.data.createUrl.id}`,
          });
          this.showSucces();
        }, 2000);
      }
    });
  };

  copyLink = () => {
    const generatedUrl = document.getElementById('generatedUrl');
    generatedUrl.select();
    document.execCommand('copy');
    message.success(`Copied the link: ${generatedUrl.value}`);
  };

  render() {
    const { styles } = this.props;
    const { visible, confirmLoading, description } = this.state;
    return (
      <span>
        <Tooltip title="Share" onClick={this.showModal}>
          <a className={styles.action}>
            <Icon type="share-alt" />
          </a>
        </Tooltip>
        <Modal
          title="Share Session Link:"
          visible={visible}
          confirmLoading={confirmLoading}
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
              <TextArea rows={2} id="description" placeholder={description} />
            </Form.Item>
          </Form>
        </Modal>
      </span>
    );
  }
}
