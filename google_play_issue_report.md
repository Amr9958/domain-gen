# تقرير: مشكلة رفض تطبيق دليل مغاغه على Google Play

---

## ملخص المشكلة

تم رفض التطبيق من Google Play بسبب وجود إذن
`ACCESS_BACKGROUND_LOCATION`
في ملف `AndroidManifest.xml`، مما يعني أن التطبيق يطلب الوصول إلى موقع المستخدم حتى وهو لا يستخدم التطبيق.

---

## السبب الجذري

في ملف `android/app/src/main/AndroidManifest.xml` يوجد أو كان يوجد السطر التالي:

```xml
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"/>
```

هذا الإذن يُعطي التطبيق صلاحية الوصول لموقع المستخدم في الخلفية (Background)،
وهو أمر تشترط Google تبريره بوظيفة أساسية لا يعمل التطبيق بدونها.

---

## المشاكل التي سببها هذا الإذن

### 1. رفض النشر – Feature doesn't meet requirements
Google رفضت التطبيق لأن وظيفة التطبيق (دليل خدمات محلية) لا تستلزم الوصول للموقع في الخلفية.
الوصول للموقع أثناء الاستخدام (Foreground) كافٍ تمامًا.

### 2. Missing Prominent Disclosure
لم يكن هناك نافذة تشرح للمستخدم سبب طلب الموقع قبل منح الإذن.
Google تشترط عرض هذا الإشعار بشكل واضح قبل أي طلب للصلاحية.

### 3. Privacy Policy ناقصة
سياسة الخصوصيه لم تذكر أن التطبيق يجمع بيانات الموقع، ولا لأي غرض تُستخدم.
هذا مخالف لسياسة User Data الخاصة بـ Google Play.

---

## المطلوب تنفيذه

### أولاً: AndroidManifest.xml
احذف أو تأكد من حذف السطر التالي من **جميع** الـ tracks (production, closed, open):
```xml
<!-- احذف هذا السطر نهائياً -->
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION"/>
```

أبقِ فقط على:
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
```

### ثانياً: Prominent Disclosure Dialog
أضف `LocationDisclosureDialog` (الملف المرفق) وناديها قبل كل طلب صلاحية موقع:
```dart
// بدلاً من:
context.read<LocationCubit>().requestPermission();

// استخدم:
await LocationDisclosureDialog.show(context);
```

### ثالثاً: Privacy Policy
حدّث سياسة الخصوصيه (الملف المرفق) لتشمل قسم "Location Data" الذي يوضح:
- أن التطبيق يجمع الموقع أثناء الاستخدام فقط (Foreground)
- أن البيانات لا تُخزَّن ولا تُشارَك
- كيفية إلغاء الإذن

---

## ملاحظة مهمة
الكود الحالي في `location_cubit.dart` صحيح ولا يطلب Background Location.
المشكلة كانت فقط في `AndroidManifest.xml` + غياب الـ Disclosure + سياسة الخصوصيه.

---

## الملفات المرفقة
- `privacy_policy_updated.html` — سياسة الخصوصيه المحدّثة
- `location_disclosure_dialog.dart` — نافذة الموافقة الصريحة للمستخدم
