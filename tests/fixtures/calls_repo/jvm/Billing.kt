package shop

open class Account

interface Auditable

class Savings : Account() {
    fun accrue() = compound()

    fun compound(): Int = 1
}

class Ledger : Account(), Auditable {
    fun post() = auditTotal()
}

fun auditTotal() = 1
