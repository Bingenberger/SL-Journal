# kotlinx.serialization: Serializer der Datenklassen behalten.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers @kotlinx.serialization.Serializable class de.sljournal.android.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
-keepclasseswithmembers class de.sljournal.android.** {
    kotlinx.serialization.KSerializer serializer(...);
}
