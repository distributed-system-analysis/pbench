"""
This module provides convenience functions that interface to lower-level services, provided by the boto3 module.
"""
import boto3
import os
import sys
import glob
import base64
import hashlib
import shutil
import time
import configtools
from datetime import datetime
from configparser import ConfigParser


class Entry(object):
    """
    An Entry object consists of a name (of an S3 object) and the MD5 value of that object. It is used to create an object with the name and MD5 value, so that it can be compared with other similar objects.
    """
    def __init__(self, name, md5):
        self.name = name
        self.md5 = md5

    def __eq__(self, other):
        return self.name == other.name and self.md5 == other.md5


class S3Connector(object):
    def __init__(self, access_key_id, secret_access_key, endpoint_url, bucket_name):
        self.s3connector = boto3.client('s3',
                                        aws_access_key_id='{}'.format(
                                            access_key_id),
                                        aws_secret_access_key='{}'.format(
                                            secret_access_key),
                                        endpoint_url='{}'.format(endpoint_url))

    def list_objects(self, **kwargs):
        return self.s3connector.list_objects_v2(**kwargs)

    def put_object(self, Bucket, Key, Body, ContentMD5):
        return self.s3connector.put_object(Bucket=Bucket, Key=Key,
                Body=Body, ContentMD5=ContentMD5)

    def head_bucket(self, Bucket):
        return self.s3connector.head_bucket(Bucket=Bucket)

    def get_object(self, Bucket, Key):
        return self.s3connector.get_object(Bucket=Bucket, Key=Key)

    def getsize(self, tar):
        return os.path.getsize(tar)


class MockS3Connector(object):
    """
    The mock object is used for unit testing. It provides a "connector" to the backend service that is implemented using the local filesystem, rather than dispatching to the real S3 backend service.
    """

    def __init__(self, access_key_id, secret_access_key, endpoint_url, bucket_name):
        self.path = endpoint_url
        self.bucket_name = bucket_name

    def create_ob_dict_for_list_objects(self, ob_dict, bucketpath,
    result_list):
        result_name_list = []
        for i in result_list:
            with open(i, 'rb') as f:
                data = f.read()
                md5 = hashlib.md5(data).hexdigest()
            result_name_list.append({'ETag': '"{}"'.format(md5),
                                     'Key': os.path.relpath(i, start=bucketpath)})
        ob_dict['Contents'] = result_name_list
        ob_dict['ResponseMetadata'] = {'HTTPStatusCode': 400}
        return ob_dict

    def list_objects(self, **kwargs):
        ob_dict = {}
        bucketpath = os.path.join(self.path, kwargs['Bucket'])
        result_list = glob.glob(os.path.join(bucketpath, "*/*.tar.xz"))
        result_list.sort()
        if kwargs['Bucket'] == "SPECIAL_BUCKET":
            if 'ContinuationToken' in kwargs.keys():
                resp = self.create_ob_dict_for_list_objects(ob_dict,
                                                      bucketpath,
                                                      result_list[2:])
                return resp
            else:
                resp = self.create_ob_dict_for_list_objects(ob_dict,
                                                      bucketpath,
                                                      result_list[:2])
                resp['NextContinuationToken'] = 'yes'
                return resp
        else:
            resp = self.create_ob_dict_for_list_objects(ob_dict,
                                                   bucketpath,
                                                   result_list[:])
            return resp

    def put_object(self, Bucket=None, Key=None, Body=None, ContentMD5=None):
        md5_hex_value = hashlib.md5(Body.read()).hexdigest()
        md5_base64_value = (base64.b64encode(
                        bytes.fromhex(md5_hex_value))).decode()
        if md5_base64_value == ContentMD5:
            test_controller = Key.split("/")[0]
            try:
                os.mkdir("{}/{}/{}".format(self.path,
                                           self.bucket_name, test_controller))
            except FileExistsError:
                # directory already exists, ignore
                pass
            with open('{}/{}/{}'.format(self.path, self.bucket_name, Key), 'wb') as f:
                f.write(Body.read())

    def head_bucket(self, Bucket):
        if os.path.exists(os.path.join(self.path, Bucket)):
            ob_dict = {}
            ob_dict['ResponseMetadata'] = {'HTTPStatusCode': 200}
            return ob_dict
        else:
            raise Exception("Bucket: {} doesn't exist".format(
                os.path.join(self.path, Bucket)))

    def get_object(self, Bucket, Key):
        ob_dict = {}
        result_path = os.path.join(self.path, Bucket, Key)
        with open(result_path, 'rb') as f:
            data = f.read()
            md5 = hashlib.md5(data).hexdigest()
        ob_dict['ResponseMetadata'] = {'HTTPStatusCode': 200}
        ob_dict['ETag'] = '"{}"'.format(md5)
        return ob_dict

    def getsize(self, tar):
        if '6.12' in tar:
            return 6442450944  # equivalent to 6 GB
        else:
            return os.path.getsize(tar)


class S3Config(object):
    def __init__(self, config):
        try:
            debug_unittest = config.get('pbench-server', 'debug_unittest')
        except Exception as e:
            debug_unittest = False
        else:
            debug_unittest = bool(debug_unittest)

        self.endpoint_url = config.get('pbench-server-backup', 'endpoint_url')
        self.bucket_name = config.get('pbench-server-backup', 'bucket_name')
        self.access_key_id = config.get('pbench-server-backup', 'access_key_id')
        self.secret_access_key = config.get('pbench-server-backup', 'secret_access_key')

        if debug_unittest:
            self.connector = MockS3Connector(
                self.access_key_id, self.secret_access_key, self.endpoint_url, self.bucket_name)
        else:
            self.connector = S3Connector(
                self.access_key_id, self.secret_access_key, self.endpoint_url, self.bucket_name)
