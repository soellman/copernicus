import time
class Session(object):
    """
    Session object are owned by the SessionHandler and maintains a state
    between client request. All requests are assigned a session and its lifetime
    is at least one request long.
    """
    def __init__(self, uid):
        self.uid = uid
        self.data = dict()
        self.create_timestamp = int(time.time())

    def __contains__(self, key):
        return key in self.data

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def get(self, key, default=None):
        """
        @return session value with given key, or default or none if not such key
        exists.
        """
        return self.data.get(key, default)


    def set(self, key, value):
        """
        Sets the given key to given value
        """
        self.data[key] = value

class SessionHandler(object):
    """
    Handles all the sessions
    """
    def __init__(self):
        self.sessions = dict()

    def getSession(self, uid, auto_create=False):
        """
        """
        try:
            #TODO: expiration
            return self.sessions[uid]
        except KeyError as e:
            if not auto_create:
                raise
            return self.createSession(uid)


    def createSession(self, uid):
        """
        Creates a session with the given uid
        @return the newly creates session
        """
        session = self.sessions[uid] = Session(uid)
        return session