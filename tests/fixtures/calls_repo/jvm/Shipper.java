package shop;

class Carrier {}

interface Trackable {}

public class Shipper extends Carrier implements Trackable {
    public void ship() {
        load();
    }

    public void load() {}
}

class Dispatcher {
    void dispatch(Shipper s) {
        s.ship();
    }
}
