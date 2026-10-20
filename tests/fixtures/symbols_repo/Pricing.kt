package shop

import kotlin.math.round

const val VAT = 0.2

fun String.slug(): String = lowercase().replace(" ", "-")

fun gross(net: Double): Double {
    return round(net * (1 + VAT) * 100) / 100
}

class PriceList(private val prices: Map<String, Double>) {
    fun price(sku: String): Double = prices.getValue(sku)

    companion object {
        fun empty() = PriceList(emptyMap())
    }
}

object Currency {
    fun symbol(): String = "EUR"
}

interface Discount {
    fun apply(net: Double): Double
}
