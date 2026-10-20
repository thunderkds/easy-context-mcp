package shop;

import java.util.HashMap;
import java.util.Map;

/** Stock levels per sku. */
public class Warehouse implements Store {
    private final Map<String, Integer> stock = new HashMap<>();

    /** Add units of one sku. */
    @Override
    public void put(String sku, int units) {
        stock.merge(sku, units, Integer::sum);
    }

    public void put(String sku) {
        put(sku, 1);
    }

    public int units(String sku) {
        return stock.getOrDefault(sku, 0);
    }
}

interface Store {
    void put(String sku, int units);
}
