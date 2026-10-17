package com.loxpanel.spike

import java.util.UUID

/** Nur eine Closure im lokalen Hauptdokument erhaelt diesen Seitenzugang. */
class IntercomCapability {
    @Volatile private var value: String? = null

    fun rotate(): String = UUID.randomUUID().toString().also { value = it }
    fun clear() { value = null }
    fun accepts(candidate: String?): Boolean = candidate != null && value != null && candidate == value
}
