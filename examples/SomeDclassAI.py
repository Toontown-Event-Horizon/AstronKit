from astronkit_data.AstronStubsAI import StubSomeDclassAI


class SomeDclassAI(StubSomeDclassAI):
    def magicMethod(self, arg0: int, arg1: int, /) -> object:
        pass

    def secondMethod(self, arg0: str, /) -> object:
        pass

    def doSomething(self):
        self.sendUpdate("magicResponse", (b"abc",))
