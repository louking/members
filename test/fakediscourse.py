'''
fakediscourse - minimal stand-in for a fluent_discourse-style client, for tests

fluent_discourse builds request paths by chaining attribute access and ._(id) calls
(e.g. discourse.c._(str(id)).show.json.get({})), only issuing a real HTTP call on a
terminal .get()/.post()/.put()/.delete(). FakeDiscourse mimics the chaining and
records/serves canned responses keyed by the dotted path, so members' own code
(run_query_paged, fetch_categories, etc.) can be tested without a network call.
'''


class FakeDiscourse:
    def __init__(self, responses, calls=None, path=None):
        self._responses = responses
        self._calls = calls if calls is not None else []
        self._path = path if path is not None else []

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return FakeDiscourse(self._responses, self._calls, self._path + [name])

    def _(self, arg):
        return FakeDiscourse(self._responses, self._calls, self._path + [str(arg)])

    def get(self, params=None):
        return self._call('get', params)

    def post(self, body=None):
        return self._call('post', body)

    def put(self, body=None):
        return self._call('put', body)

    def delete(self, params=None):
        return self._call('delete', params)

    def _call(self, method, arg):
        path = '.'.join(self._path)
        self._calls.append((path, method, arg))
        # prefer a (path, method)-specific response (needed when the same fluent
        # path is used for more than one HTTP verb, e.g. PUT to add group members
        # and DELETE to remove them both hit groups.<id>.members.json), falling
        # back to a path-only response for the common single-verb-per-path case
        if (path, method) in self._responses:
            resp = self._responses[(path, method)]
        else:
            resp = self._responses.get(path)
        if callable(resp):
            return resp(arg)
        if resp is None:
            raise KeyError(f'FakeDiscourse: no response configured for {method} {path!r}')
        return resp
