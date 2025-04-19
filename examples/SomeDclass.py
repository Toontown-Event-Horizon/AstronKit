from astronkit_data.AstronStubsCL import StubSomeDclass


class SomeDclass(StubSomeDclass):
    def magicResponse(self, arg0: bytes, /) -> object:
        pass

    def doSomething(self):
        self.sendUpdate("magicMethod", (1, 2))
