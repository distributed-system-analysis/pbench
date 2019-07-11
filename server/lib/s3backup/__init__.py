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
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ConnectionClosedError, ClientError

from enum import Enum


class Status(Enum):
    SUCCESS = 0
    FAIL = 1


class Entry(object):
    """An Entry object consists of a name (of an S3 object) and the MD5
    value of that object. It is used to create an object with the name
    and MD5 value, so that it can be compared with other similar
    objects.

    """

    def __init__(self, name, md5):
        self.name = name
        self.md5 = md5

    def __eq__(self, other):
        return self.name == other.name and self.md5 == other.md5


class S3Config(object):

    GB = 1024 ** 3
    MB = 1024 ** 2

    def __init__(self, config, logger):
        try:
            debug_unittest = config.get('pbench-server', 'debug_unittest')
        except Exception as e:
            debug_unittest = False
        else:
            debug_unittest = bool(debug_unittest)

        self.chunk_size = 256 * self.MB
        self.multipart_threshold = 5 * self.GB
        self.bucket_name = config.get('pbench-server-backup', 'bucket_name')
        self.transfer_config = TransferConfig(
            multipart_threshold=self.multipart_threshold,
            multipart_chunksize=self.chunk_size)
        self.logger = logger
        if debug_unittest:
            self.connector = MockS3Connector(config)
        else:
            self.connector = S3Connector(config)

    def getsize(self, tar):
        return self.connector.getsize(tar)

    # pass through to the corresponding connector method
    def get_tarball_header(self,  Bucket=None, Key=None):
        return self.connector.get_object(Bucket=Bucket, Key=Key)

    @staticmethod
    def calculate_multipart_etag(tb, chunk_size):
        md5s = []

        with open(tb, 'rb') as fp:
            while True:
                data = fp.read(chunk_size)
                if not data:
                    break
                md5s.append(hashlib.md5(data))

            if len(md5s) > 1:
                digests = b"".join(m.digest() for m in md5s)
                new_md5 = hashlib.md5(digests)
                new_etag = '%s-%s' % (new_md5.hexdigest(), len(md5s))
            elif len(md5s) == 1:
                # file smaller than chunk size
                new_etag = '"%s"' % md5s[0].hexdigest()
            else:
                new_etag = ''

        return new_etag

    def put_tarball(self, Name=None, Body=None, Size=0, ContentMD5=None, Bucket=None, Key=None):
        md5_base64_value = (base64.b64encode(
            bytes.fromhex(ContentMD5))).decode()
        if Size < (5 * self.GB):
            try:
                self.connector.put_object(
                    Bucket=self.bucket_name, Key=Key, Body=Body, ContentMD5=md5_base64_value)
            except ConnectionClosedError:
                # This is a transient failure and will be retried at
                # the next invocation of the backups.
                self.logger.error("Upload to s3 failed, connection was reset"
                                   " while transferring {key}".format(key=Key))
                return Status.FAIL
            except Exception:
                # What ever the reason is for this failure, the
                # operation will be retried the next time backups
                # are run.
                self.logger.exception("Upload to S3 failed"
                                      " while transferring {key}".format(key=Key))
                return Status.FAIL
            else:
                self.logger.info(
                    "Upload to s3 succeeded: {key}".format(key=Key))
                return Status.SUCCESS
        else:
            # calculate multi etag value
            etag = self.calculate_multipart_etag(Name, self.chunk_size)
            try:
                self.connector.upload_fileobj(
                    Body=Body,
                    Bucket=Bucket,
                    Key=Key,
                    Config=self.transfer_config,
                    ExtraArgs={
                        'Metadata': {
                            'ETag': etag,
                            'MD5': ContentMD5
                        }
                    })
            except ClientError as e:
                self.logger.error(
                    "Multi-upload to s3 failed, client error: {}".format(e))
                return Status.FAIL
            else:
                # compare the multi etag value uploaded in metadata
                # field with s3 etag for data integrity.
                try:
                    obj = self.connector.get_object(
                        Bucket=self.bucket_name, Key=Key)
                except Exception:
                    self.logger.exception("get_object failed: {}".format(Key))
                    return Status.FAIL
                else:
                    s3_multipart_etag = obj['ETag']
                    if s3_multipart_etag == etag:
                        self.logger.info("Multi-upload to s3 succeeded: "
                                         "{key}".format(key=Key))
                        return Status.SUCCESS
                    else:
                        # delete object from s3 and move to specific
                        # state directory for retry
                        self.connector.delete_object(
                            Bucket=self.bucket_name, Key=Key)
                        self.logger.error("Multi-upload to s3 failed:"
                                          " {key}, etag doesn't match".format(key=Key))
                        return Status.FAIL

    # pass through to the corresponding connector
    def head_bucket(self, Bucket=None):
        return self.connector.head_bucket(Bucket=Bucket)

    def list_objects(self, **kwargs):
        return self.connector.list_objects(**kwargs)

###########################################################################
# Connectors start here.
###########################################################################

# abstract connector class


class Connector(object):
    def __init__(self):
        pass

    def list_objects(self, **kwargs):
        pass

    def head_bucket(self, Bucket=None):
        pass

    def get_object(self, Bucket=None, Key=None):
        return self.s3client.get_object(Bucket=Bucket, Key=Key)

    def put_object(self, Bucket=None, Key=None, Body=None, ContentMD5=None):
        pass

    def upload_fileobj(self, Body=None, Bucket=None, Key=None,
                       Config=None, ExtraArgs=None):
        pass

    def delete_object(self, Bucket=None, Key=None):
        pass

    def getsize(self, tb):
        return os.path.getsize(tb)

# Connector to the S3 service.


class S3Connector(Connector):
    def __init__(self, config):
        self.endpoint_url = config.get('pbench-server-backup', 'endpoint_url')
        self.bucket_name = config.get('pbench-server-backup', 'bucket_name')
        self.access_key_id = config.get(
            'pbench-server-backup', 'access_key_id')
        self.secret_access_key = config.get(
            'pbench-server-backup', 'secret_access_key')
        self.s3client = boto3.client('s3',
                                     aws_access_key_id='{}'.format(
                                         self.access_key_id),
                                     aws_secret_access_key='{}'.format(
                                         self.secret_access_key),
                                     endpoint_url='{}'.format(self.endpoint_url))
        self.transfer_config = None

    def list_objects(self, **kwargs):
        return self.s3client.list_objects_v2(**kwargs)

    def head_bucket(self, Bucket=None):
        return self.s3client.head_bucket(Bucket=Bucket)

    def get_object(self, Bucket=None, Key=None):
        return self.s3client.get_object(Bucket=Bucket, Key=Key)

    def put_object(self, Body=None, ContentMD5=None, Bucket=None, Key=None):
        return self.s3client.put_object(Bucket=Bucket, Key=Key,
                                        Body=Body,
                                        ContentMD5=ContentMD5)

    def upload_fileobj(self, Body=None, Bucket=None, Key=None,
                       Config=None, ExtraArgs=None):
        return self.s3client.upload_fileobj(Body=Body, Bucket=Bucket,
                                            Key=Key, Config=Config,
                                            ExtraArgs=ExtraArgs)

    def delete_object(self, Bucket=None, Key=None):
        return self.s3client.delete_object(Bucket=Bucket, Key=Key)

# Connector to the mock "S3" service for unit testing.


class MockS3Connector(Connector):
    """
    The mock object is used for unit testing. It provides a "connector"
    to the backend service that is implemented using the local
    filesystem, rather than dispatching to the real S3 backend
    service.
    """

    # class "constant"
    GB = 1024 ** 3

    def __init__(self, config):
        self.path = config.get('pbench-server-backup', 'endpoint_url')
        self.bucket_name = config.get('pbench-server-backup', 'bucket_name')

    def list_objects(self, **kwargs):
        ob_dict = {}
        bucketpath = os.path.join(self.path, kwargs['Bucket'])
        result_list = glob.glob(os.path.join(bucketpath, "*/*.tar.xz"))
        result_list.sort()
        # we pretend that objects in the SPECIAL_BUCKET are large objects.
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

    @staticmethod
    def create_ob_dict_for_list_objects(ob_dict, bucketpath, result_list):
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
            return Status.SUCCESS
        return Status.FAIL

    def upload_fileobj(self, Body=None, Bucket=None, Key=None, Config=None, ExtraArgs=None):
        test_controller = Key.split("/")[0]
        try:
            os.mkdir("{}/{}/{}".format(self.path,
                                       self.bucket_name,
                                       test_controller))
        except FileExistsError:
            # directory already exists, ignore
            pass
        with open('{}/{}/{}'.format(self.path, self.bucket_name, Key), 'wb') as f:
            f.write(Body.read())
        with open('{}/{}/{}.multiEtag'.format(self.path, self.bucket_name, Key), 'w') as f:
            if "6.13" in Key:
                pass
            else:
                f.write('{} {}'.format(ExtraArgs['Metadata']['ETag'],
                                       ExtraArgs['Metadata']['MD5']))

    def head_bucket(self, Bucket=None):
        if os.path.exists(os.path.join(self.path, Bucket)):
            ob_dict = {}
            ob_dict['ResponseMetadata'] = {'HTTPStatusCode': 200}
            return ob_dict
        else:
            raise Exception("Bucket: {} doesn't exist".format(
                os.path.join(self.path, Bucket)))

    def get_object(self, Bucket=None, Key=None):
        ob_dict = {}
        result_path = os.path.join(self.path, Bucket, Key)
        with open(result_path, 'rb') as f:
            data = f.read()
            md5 = hashlib.md5(data).hexdigest()
        ob_dict['ResponseMetadata'] = {'HTTPStatusCode': 200}
        multi_etag_file = '{}/{}/{}.multiEtag'.format(
                                                self.path,
                                                self.bucket_name,
                                                Key)
        if os.path.exists(multi_etag_file):
            with open(multi_etag_file) as f:
                multi_etag_value = f.read().split(" ")[0]
            ob_dict['ETag'] = '"{}"'.format(multi_etag_value.strip("\""))
        else:
            ob_dict['ETag'] = '"{}"'.format(md5)
        return ob_dict

    def getsize(self, tar):
        if '6.12' in tar:
            return 6442450944  # equivalent to 6 GB
        else:
            return os.path.getsize(tar)
