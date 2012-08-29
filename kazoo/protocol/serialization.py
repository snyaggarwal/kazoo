"""Zookeeper Serializers, Deserializers, and NamedTuple objects"""
from collections import namedtuple
import struct

from kazoo.protocol.states import ZnodeStat


# Struct objects with formats compiled
int_struct = struct.Struct('!i')
int_int_struct = struct.Struct('!ii')
int_int_long_struct = struct.Struct('!iiq')

int_long_int_long_struct = struct.Struct('!iqiq')
reply_header_struct = struct.Struct('!iqi')
stat_struct = struct.Struct('!qqqqiiiqiiq')


def read_string(buffer, offset):
    """Reads an int specified buffer into a string and returns the
    string and the new offset in the buffer"""
    length = int_struct.unpack_from(buffer, offset)[0]
    offset += int_struct.size
    if length < 0:
        return None, offset
    else:
        index = offset
        offset += length
        return str(buffer[index:index + length].decode('utf-8')), offset


def write_acl(acl):
    b = bytearray()
    b.extend(int_struct.pack(acl.perms))


def write_string(bytes):
    if not bytes:
        return int_struct.pack(-1)
    else:
        utf8_str = bytes.encode('utf-8')
        return int_struct.pack(len(utf8_str)) + utf8_str


def write_buffer(bytes):
    if not bytes:
        return int_struct.pack(-1)
    else:
        return int_struct.pack(len(bytes)) + bytes


def read_buffer(bytes, offset):
    length = int_struct.unpack_from(bytes, offset)[0]
    offset += int_struct.size
    if length < 0:
        return None, offset
    else:
        index = offset
        offset += length
        return bytes[index:index + length], offset


class Connect(namedtuple('Connect', 'protocol_version last_zxid_seen'
                         ' time_out session_id passwd read_only')):
    """A connection request"""
    type = None

    def serialize(self):
        b = bytearray()
        b.extend(int_long_int_long_struct.pack(
            self.protocol_version, self.last_zxid_seen, self.time_out,
            self.session_id))
        b.extend(write_buffer(self.passwd))
        b.extend([1 if self.read_only else 0])
        return b

    @classmethod
    def deserialize(cls, bytes, offset):
        proto_version, timeout, session_id = int_int_long_struct.unpack_from(
            bytes, offset)
        offset += int_int_long_struct.size
        password, offset = read_buffer(bytes, offset)
        return cls(proto_version, 0, timeout, session_id, password, 0), offset


class Create(namedtuple('Create', 'path data acl flags')):
    type = 1

    def serialize(self):
        b = bytearray()
        b.extend(write_string(self.path))
        b.extend(write_buffer(self.data))
        b.extend(int_struct.pack(len(self.acl)))
        for acl in self.acl:
            b.extend(int_struct.pack(acl.perms) + write_string(acl.id.scheme)
                     + write_string(acl.id.id))
        b.extend(int_struct.pack(self.flags))
        return b

    @classmethod
    def deserialize(cls, bytes, offset):
        return read_string(bytes, offset)[0]


class GetChildren(namedtuple('GetChildren', 'path children watcher')):
    type = 8

    def serialize(self):
        b = bytearray()
        b.extend(write_string(self.path))
        b.extend([1 if self.watcher else 0])
        return b

    @classmethod
    def deserialize(cls, bytes, offset):
        count = int_struct.unpack_from(bytes, offset)[0]
        offset += int_struct.size
        if count == -1:
            return []

        children = []
        for c in range(count):
            child, offset = read_string(bytes, offset)
            children.append(child)
        return children


class Exists(namedtuple('Exists', 'path watcher')):
    type = 3

    def serialize(self):
        b = bytearray()
        b.extend(write_string(self.path))
        b.extend([1 if self.watcher else 0])
        return b

    @classmethod
    def deserialize(cls, bytes, offset):
        stat = ZnodeStat._make(stat_struct.unpack_from(bytes, offset))
        return stat if stat.czxid != -1 else None


class Close(object):
    __slots__ = ['type']
    type = -11

    @classmethod
    def serialize(cls):
        return ''


class Ping(object):
    __slots__ = ['type']
    type = 11

    @classmethod
    def serialize(cls):
        return ''


class Watch(namedtuple('Watch', 'type state path')):
    @classmethod
    def deserialize(cls, buffer, offset):
        """Given a buffer and the current buffer offset, return the type,
        state, path, and new offset"""
        type, state = int_int_struct.unpack_from(buffer, offset)
        offset += int_int_struct.size
        path, offset = read_string(buffer, offset)
        return cls(type, state, path), offset


class ReplyHeader(namedtuple('ReplyHeader', 'xid, zxid, err')):
    @classmethod
    def deserialize(cls, buffer, offset):
        """Given a buffer and the current buffer offset, return a
        :class:`ReplyHeader` instance and the new offset"""
        new_offset = offset + reply_header_struct.size
        return cls._make(
            reply_header_struct.unpack_from(buffer, offset)), new_offset
