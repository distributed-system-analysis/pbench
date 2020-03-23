"""
This module provides convenience functions that interface to lower-level services, provided by the boto3 module.
"""
import base64
import glob
import hashlib
import os
from configparser import NoOptionError, NoSectionError
from enum import Enum

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError, ConnectionClosedError


class Status(Enum):
    SUCCESS = 0
    FAIL = 1


class NoSuchKey(Exception):
    pass


class MockGetObjectException(Exception):
    """A generic exception for testing - only raised by the mocked get_object()
    so that get_tarball_header() can be tested.
    """

    pass


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

    def __str__(self):
        return "{} :: {}".format(self.name, self.md5)


class S3Config(object):

    GB = 1024 ** 3
    MB = 1024 ** 2

    def __init__(self, config, logger):
        try:
            debug_unittest = config.get("pbench-server", "debug_unittest")
        except Exception:
            debug_unittest = False
        else:
            debug_unittest = bool(debug_unittest)

        self.chunk_size = 256 * self.MB
        self.multipart_threshold = 5 * self.GB
        self.transfer_config = TransferConfig(
            multipart_threshold=self.multipart_threshold,
            multipart_chunksize=self.chunk_size,
        )
        self.logger = logger
        if debug_unittest:
            self.connector = MockS3Connector(config, logger)
        else:
            self.connector = S3Connector(config, logger)

        # Normally, the connector defines a bucket_name attribute as
        # specified in the config file.  The application layer does
        # not know anything about the connector and we want to keep it
        # that way, but it has to know the bucket_name because it
        # executes a head_bucket() call on it, in order to figure out
        # whether S3 is enabled and whether the bucket exists and is
        # accessible. So we copy the bucket_name here so that it can
        # be accessed by the application layer, but if bucket_name is
        # not defined at all (which is possible when we deliberately
        # turn off the S3 backup by deleting the relevant section in
        # the config file), we would get an AttributeError exception
        # here. We don't want to abort the application though: it might
        # still want to continue with local backups, so we  catch the
        # exception and set the bucket_name to None in that case. The
        # application will have to check for that.
        try:
            self.bucket_name = self.connector.bucket_name
        except AttributeError:
            self.bucket_name = None

    def getsize(self, tar):
        return self.connector.getsize(tar)

    # pass through to the corresponding connector method
    def get_tarball_header(self, Bucket=None, Key=None):
        try:
            resp = self.connector.get_object(Bucket=Bucket, Key=Key)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise NoSuchKey
            else:
                raise
        except Exception:
            raise
        else:
            return resp

    def put_tarball(
        self, Name=None, Body=None, Size=0, ContentMD5=None, Bucket=None, Key=None
    ):

        if Size < (5 * self.GB):
            try:
                # The S3 put_object() expects ContentMD5 to be base64-encoded.
                self.connector.put_object(
                    Bucket=self.bucket_name,
                    Key=Key,
                    Body=Body,
                    ContentMD5=s3_contentMD5(ContentMD5),
                )
            except ConnectionClosedError:
                # This is a transient failure and will be retried at
                # the next invocation of the backups.
                self.logger.error(
                    "Upload to s3 failed, connection was reset"
                    " while transferring {}",
                    Key,
                )
                return Status.FAIL
            except Exception:
                # What ever the reason is for this failure, the
                # operation will be retried the next time backups
                # are run.
                self.logger.exception(
                    "Upload to S3 failed" " while transferring {}", Key
                )
                return Status.FAIL
            else:
                self.logger.info("Upload to s3 succeeded: {}", Key)
                return Status.SUCCESS
        else:
            # calculate multi etag value
            etag = self.connector.calculate_multipart_etag(Name, self.chunk_size)
            if not etag:
                return Status.FAIL
            try:
                self.connector.upload_fileobj(
                    Body=Body,
                    Bucket=Bucket,
                    Key=Key,
                    Config=self.transfer_config,
                    ExtraArgs={
                        "Metadata": {
                            # S3 insists on lower-casing these field names, so
                            # we succumb in order to avoid confusion.
                            "etag": etag,
                            "md5": ContentMD5,
                        }
                    },
                )
            except ClientError as e:
                self.logger.error("Multi-upload to s3 failed, client error: {}", e)
                return Status.FAIL
            else:
                # compare the multi etag value uploaded in metadata
                # field with s3 etag for data integrity.
                try:
                    obj = self.connector.get_object(Bucket=self.bucket_name, Key=Key)
                except Exception:
                    self.logger.exception("get_object failed: {}", Key)
                    return Status.FAIL
                else:
                    # The ETag value is wrapped in double quotes
                    # so we get rid of them here.
                    s3_multipart_etag = obj["ETag"].strip('"')
                    if s3_multipart_etag == etag:
                        self.logger.info("Multi-upload to s3 succeeded: {}", Key)
                        return Status.SUCCESS
                    else:
                        # delete object from s3
                        # TBD: this should be flagged for retry, but
                        # currently we just fail.
                        self.connector.delete_object(Bucket=self.bucket_name, Key=Key)
                        self.logger.error(
                            "Multi-upload to s3 failed: {}, etag doesn't match", Key
                        )
                        self.logger.debug(
                            "object ETag = {}, calculated ETag = {}",
                            s3_multipart_etag,
                            etag,
                        )
                        return Status.FAIL

    # pass through to the corresponding connector
    def head_bucket(self, Bucket=None):
        return self.connector.head_bucket(Bucket=Bucket)

    def list_objects(self, **kwargs):
        return self.connector.list_objects(**kwargs)

    # response decoding - tbh is the header returned
    # by get_tarball_header().
    @staticmethod
    def s3_md5(tbh):
        # We need to decode the response to figure out where the MD5
        # is stored: for a large object, it is in the Metadata field;
        # for a small object, it is in the ETag field, but it's
        # wrapped in double quotes which we strip.
        # tbh is the header returned by get_tarball_header().
        if "Metadata" in tbh and tbh["Metadata"]:
            if "md5" in tbh["Metadata"]:
                return tbh["Metadata"]["md5"]
            else:
                return None
        else:
            return tbh["ETag"].strip('"')

    def header_md5(self, objh):
        # the object header comes from a call to list_objects(): this
        # call returns a response whose 'Contents' field is a list of
        # object headers.  Each header contains (at least) a 'Key'
        # field, an 'ETag' field and a 'Size field. We use the 'Size'
        # field to distinguish whether the 'ETag' field contains an
        # md5 sum or not: for small objects (< 5 Gib) it does; but for
        # large objects (>= 5 Gib), we need to make an additional
        # get_tarball_header() call to get the additional metadata
        # that we store with the ExtraArgs parameter to upload_fileobj()
        # in put_tarball() above.
        if objh["Size"] < 5 * self.GB:
            return objh["ETag"].strip('"')
        else:
            try:
                obj = self.get_tarball_header(Bucket=self.bucket_name, Key=objh["Key"])
            except Exception:
                return None
            return self.s3_md5(obj)


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

    def upload_fileobj(
        self, Body=None, Bucket=None, Key=None, Config=None, ExtraArgs=None
    ):
        pass

    def delete_object(self, Bucket=None, Key=None):
        pass

    def getsize(self, tb):
        return os.path.getsize(tb)


# Connector to the S3 service.
class S3Connector(Connector):
    def __init__(self, config, logger):
        # S3 backup can be turned off by commenting out the
        # [pbench-server-backup]endpoint_url option in the config
        # file.
        try:
            self.endpoint_url = config.get("pbench-server-backup", "endpoint_url")
        except (NoSectionError, NoOptionError):
            self.endpoint_url = None
        else:
            self.bucket_name = config.get("pbench-server-backup", "bucket_name")
            self.access_key_id = config.get("pbench-server-backup", "access_key_id")
            self.secret_access_key = config.get(
                "pbench-server-backup", "secret_access_key"
            )
            self.s3client = boto3.client(
                "s3",
                aws_access_key_id="{}".format(self.access_key_id),
                aws_secret_access_key="{}".format(self.secret_access_key),
                endpoint_url="{}".format(self.endpoint_url),
            )
        self.logger = logger

    @staticmethod
    def calculate_multipart_etag(tb, chunk_size):
        md5s = []

        with open(tb, "rb") as fp:
            for data in fp.read(chunk_size):
                md5s.append(hashlib.md5(data))

        if len(md5s) > 1:
            digests = b"".join(m.digest() for m in md5s)
            new_md5 = hashlib.md5(digests)
            new_etag = "{}-{}".format(new_md5.hexdigest(), len(md5s))
        elif len(md5s) == 1:
            # file smaller than chunk size
            new_etag = md5s[0].hexdigest()
        else:
            new_etag = ""

        return new_etag

    def list_objects(self, **kwargs):
        return self.s3client.list_objects_v2(**kwargs)

    def head_bucket(self, Bucket=None):
        return self.s3client.head_bucket(Bucket=Bucket)

    def get_object(self, Bucket=None, Key=None):
        return self.s3client.get_object(Bucket=Bucket, Key=Key)

    def put_object(self, Bucket=None, Key=None, Body=None, ContentMD5=None):
        return self.s3client.put_object(
            Bucket=Bucket, Key=Key, Body=Body, ContentMD5=ContentMD5
        )

    def upload_fileobj(
        self, Body=None, Bucket=None, Key=None, Config=None, ExtraArgs=None
    ):
        return self.s3client.upload_fileobj(
            Body, Bucket, Key, Config=Config, ExtraArgs=ExtraArgs
        )

    def delete_object(self, Bucket=None, Key=None):
        return self.s3client.delete_object(Bucket=Bucket, Key=Key)


# Connector to the mock "S3" service for unit testing.
class MockS3Connector(Connector):
    """The mock object is used for unit testing. It provides a "connector"
    to the backend service that is implemented using the local
    filesystem, rather than dispatching to the real S3 backend
    service.

    We store the "object" as a file together with an ETag file. For
    "small" objects, we store the MD5sum of the file (with double
    quotes wrapping it, just as the real S3 service returns it) in the
    ETag file.  For "large" objects, we store a deliberately modified
    md5sum (we bump up the first digit to the next hex digit, wrapping
    around to 0 if necessary).

    """

    # class "constant"
    GB = 1024 ** 3

    def __init__(self, config, logger):
        try:
            self.path = config.get("pbench-server-backup", "endpoint_url")
        except (NoSectionError, NoOptionError):
            self.path = None
        else:
            self.bucket_name = config.get("pbench-server-backup", "bucket_name")
        self.logger = logger

    @staticmethod
    def calculate_multipart_etag(tb, chunk_size):
        # just return a dummy string
        return "1234567890abcde-2"

    def list_objects(self, **kwargs):
        ob_dict = {}
        bucketpath = os.path.join(self.path, kwargs["Bucket"])
        result_list = glob.glob(os.path.join(bucketpath, "*/*.tar.xz"))
        result_list.sort()
        # We pretend that SPECIAL_BUCKET contains too many objects to
        # be returned in one call: we'll need a continuation call to get
        # them all.
        if kwargs["Bucket"] == "SPECIAL_BUCKET":
            if "ContinuationToken" in kwargs.keys():
                # return all but the first object
                resp = self.create_ob_dict_for_list_objects(
                    ob_dict, bucketpath, result_list[2:]
                )
                # ... and indicate that there are no more objects.
                resp["IsTruncated"] = False
                return resp
            else:
                # return just the first object
                resp = self.create_ob_dict_for_list_objects(
                    ob_dict, bucketpath, result_list[:2]
                )
                # ... and indicate that there are more objects.
                resp["IsTruncated"] = True
                resp["NextContinuationToken"] = "yes"
                return resp
        else:
            resp = self.create_ob_dict_for_list_objects(
                ob_dict, bucketpath, result_list[:]
            )
            return resp

    @staticmethod
    def create_ob_dict_for_list_objects(ob_dict, bucketpath, result_list):
        result_name_list = []
        for i in result_list:
            etag_file = "{}.ETag".format(i)
            with open(etag_file) as f:
                etag = f.read()[:-1]

            # prepare to lie about the size: if there is a <foo>.tar.xz.MD5
            # file, this is a Large Object, so we set the size to 6Gib.
            md5_file = "{}.MD5".format(i)
            if os.path.exists(md5_file):
                size = 6442450944  # equivalent to 6 GB
            else:
                size = os.path.getsize(i)
            result_name_list.append(
                {
                    "ETag": etag,
                    "Size": size,
                    "Key": os.path.relpath(i, start=bucketpath),
                }
            )
        ob_dict["Contents"] = result_name_list
        ob_dict["ResponseMetadata"] = {"HTTPStatusCode": 200}
        return ob_dict

    def put_object(self, Bucket=None, Key=None, Body=None, ContentMD5=None):
        if not self.path:
            return Status.FAIL
        barray = Body.read()
        md5 = hashlib.md5(barray).hexdigest()
        if s3_contentMD5(md5) == ContentMD5:
            test_controller = Key.split("/")[0]
            try:
                os.mkdir(
                    "{}/{}/{}".format(self.path, self.bucket_name, test_controller)
                )
            except FileExistsError:
                # directory already exists, ignore
                pass

            fout = "{}/{}/{}".format(self.path, self.bucket_name, Key)
            with open(fout, "wb") as f:
                f.write(barray)

            etagfile = "{}/{}/{}.ETag".format(self.path, self.bucket_name, Key)
            with open(etagfile, "w") as f:
                f.write(f'"{md5}"\n')

            return Status.SUCCESS
        return Status.FAIL

    def upload_fileobj(
        self, Body=None, Bucket=None, Key=None, Config=None, ExtraArgs=None
    ):
        if not self.path:
            return Status.FAIL
        test_controller = Key.split("/")[0]
        try:
            os.mkdir("{}/{}/{}".format(self.path, self.bucket_name, test_controller))
        except FileExistsError:
            # directory already exists, ignore
            pass
        etag = ExtraArgs["Metadata"]["etag"]
        with open("{}/{}/{}".format(self.path, self.bucket_name, Key), "wb") as f:
            f.write(Body.read())
        with open("{}/{}/{}.ETag".format(self.path, self.bucket_name, Key), "w") as f:
            # N.B. the double quotes are intentional: they simulate
            # what the real S3 service does with the ETag field.
            f.write(f'"{etag}"\n')
        md5 = ExtraArgs["Metadata"]["md5"]
        with open("{}/{}/{}.MD5".format(self.path, self.bucket_name, Key), "w") as f:
            f.write(f"{md5}\n")

    def head_bucket(self, Bucket=None):
        if os.path.exists(os.path.join(self.path, Bucket)):
            ob_dict = {}
            ob_dict["ResponseMetadata"] = {"HTTPStatusCode": 200}
            return ob_dict
        else:
            raise Exception(
                "Bucket: {} doesn't exist".format(os.path.join(self.path, Bucket))
            )

    def get_object(self, Bucket=None, Key=None):
        if not self.path:
            return None
        ob_dict = {}
        result_path = os.path.join(self.path, Bucket, Key)

        # Testing error cases
        # ClientError with code "other"
        resp_other_client_error = {
            "Error": {
                "Code": "Other",
                "Message": "Other error from mocked S3 get_object()",
            }
        }
        if Key == "foo/client_error_other.tar.xz":
            raise ClientError(resp_other_client_error, "get_object")

        # some other exception
        if Key == "foo/get_object_exception.tar.xz":
            raise MockGetObjectException("Other exception from mocked S3 get_object()")

        # "real" testing begins here
        resp_no_such_key = {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "No such key from mocked S3 get_object()",
            }
        }
        if not os.path.exists(result_path):
            raise ClientError(resp_no_such_key, "get_object")

        with open(result_path, "rb") as f:
            data = f.read()
            md5 = hashlib.md5(data).hexdigest()

        ob_dict["ResponseMetadata"] = {"HTTPStatusCode": 200}
        etag_file = "{}/{}/{}.ETag".format(self.path, self.bucket_name, Key)
        md5_file = "{}/{}/{}.MD5".format(self.path, self.bucket_name, Key)

        if os.path.exists(md5_file):
            with open(etag_file) as f:
                etag = f.read()[:-1]
            with open(md5_file) as f:
                md5 = f.read()[:-1]

            ob_dict["ETag"] = etag
            # lower-case field names here to agree with S3 convention: it seems
            # to lower-case fields that are passed in ExtraArgs (see above), so
            # we follow that convention here.
            ob_dict["Metadata"] = {"etag": etag.strip('"'), "md5": md5}
        else:
            ob_dict["ETag"] = '"{}"'.format(md5)
            ob_dict["Metadata"] = {}
        return ob_dict

    def getsize(self, tar):
        # The tar  argument is a full pathname, so it contains the test number.

        # These are "large" object tests: when one is added to unittests, it also
        # needs to be added here (unless the real size of the tarball is > 5GB which
        # is NOT recommended :-) ).
        lo_tests = ["6.12", "6.15", "9.8"]
        for tst in lo_tests:
            if tst in tar:
                return 6442450944  # equivalent to 6 GB
        return os.path.getsize(tar)


# utility functions

# s3 put_object() wants a base64-encoded string.
# Argument md5 is what md5sum() returns: the hexdigest() value of the md5.
def s3_contentMD5(md5):
    # get bytes from hex, base64-encode the bytes and then
    # decode to a string - ugh...
    return (base64.b64encode(bytes.fromhex(md5))).decode()
