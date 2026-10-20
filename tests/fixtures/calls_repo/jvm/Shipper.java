package shop;

class Carrier {}

interface Trackable {}

public class Shipper extends Carrier implements Trackable {
    public void ship() {
        load();
    }

    public void load() {}

    public static Shipper create() {
        return new Shipper();
    }
}

class Dispatcher {
    void dispatch(Shipper s) {
        Shipper.create();
        s.load();
    }
}
