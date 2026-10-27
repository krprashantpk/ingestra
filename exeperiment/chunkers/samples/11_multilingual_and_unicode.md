---
description: Multilingual prose, combining characters, emoji, and special-token literals.
---

# Multilingual review examples

## English and accented words

The café keeps a résumé of its fictional review history. A naïve comparison of
character counts can miss how tokenization treats words such as Straße,
jalapeño, and déjà vu. Compare composed café with decomposed café in raw view.
They can look alike without containing the same sequence of Unicode characters.

## Hindi

यह एक काल्पनिक दस्तावेज़ की समीक्षा का उदाहरण है। समीक्षक पहले सारांश पढ़ता है
और फिर उपलब्ध प्रमाण की जाँच करता है। अधूरी जानकारी मिलने पर वह स्पष्ट प्रश्न
लिखता है। मूल पाठ को बिना बदले सुरक्षित रखना आवश्यक है।

## Chinese

这是一份虚构的文档审阅示例。审阅者先阅读摘要，再检查支持材料。
如果缺少附件，应记录缺失内容并提出明确的问题。分块不能悄悄删除原文。
不同语言的字符数量与词元数量并不相同。

## Japanese

これは架空の文書レビューの例です。担当者は要約と根拠を確認します。
情報が不足している場合は、その理由を記録して追加資料を依頼します。
元の文章と埋め込み用の文章を比較してください。

## Arabic

هذا مثال خيالي لمراجعة مستند. يقرأ المراجع الملخص ثم يتحقق من الأدلة المتاحة.
عند غياب المعلومات، يسجل سؤالا واضحا ويحتفظ بالنص الأصلي دون تغيير.

## Symbols and literal tokens

Status examples include 📄 received, 🔎 in review, and ✅ complete.
The family sequence 👩‍👩‍👧‍👦 contains multiple code points.
The strings `<|endoftext|>` and `<|fim_prefix|>` are literal document content,
not instructions to the tokenizer.

## Extended multilingual review rounds

## Round 001: Hindi

Record DOC-1001; topic: Revision identity.

यह काल्पनिक समीक्षा रिकॉर्ड उपलब्ध प्रमाण और अधूरी जानकारी को अलग रखता है। समीक्षक मूल दस्तावेज़, संशोधन की तारीख और अगले उत्तरदायी व्यक्ति का नाम दर्ज करता है। यदि कोई संलग्नक अनुपलब्ध है तो उसका अनुमान नहीं लगाया जाता। मूल पाठ और उसका क्रम सुरक्षित रहना चाहिए।

## Round 002: Chinese

Record DOC-1002; topic: Attachment recovery.

这份虚构记录说明了审阅过程中的证据和假设。审阅者先确认文档编号，再比较修改记录，并保留需要进一步说明的问题。缺少附件并不等于已有证据相互矛盾。即使分块边界出现在两个段落之间，原始文本也必须能够完整还原。

## Round 003: Japanese

Record DOC-1003; topic: Ownership handoff.

この架空の記録では、確認できた事実と今後確認する必要がある内容を区別します。担当者は文書番号、改訂日、根拠となる資料を記録します。不足している情報を推測で補わず、次の担当者が同じ文脈を理解できるようにします。元の文字列を変更しないことが重要です。

## Round 004: Arabic

Record DOC-1004; topic: Claim qualification.

يحفظ هذا السجل الخيالي الفرق بين الملاحظة والتفسير. يتحقق المراجع من رقم المستند وتاريخ المراجعة والمواد الداعمة قبل تسجيل القرار. إذا كان أحد المرفقات مفقودا، يكتب سؤالا محددا بدلا من افتراض محتواه. يجب أن يبقى النص الأصلي وترتيب الفقرات محفوظين عند تقسيم المستند.

## Round 005: French

Record DOC-1005; topic: Duplicate detection.

Le café conserve un résumé de chaque révision fictive. Une comparaison naïve ne doit pas confondre une observation vérifiée avec une interprétation provisoire. L'équipe précise quelle pièce manque et qui doit répondre. Les formes café et café peuvent sembler identiques tout en contenant des suites de points de code différentes.

## Round 006: German

Record DOC-1006; topic: Publication readiness.

Die fiktive Prüfstelle in der Straße bewahrt die ursprüngliche Begründung auf. Änderungen am Titel ersetzen weder die Dokumentkennung noch den Nachweis einer Entscheidung. Die zuständige Person beschreibt, welche Unterlagen fehlen und welche Aussage bereits überprüft wurde. Wörter, Umlaute und Absatzreihenfolge bleiben unverändert.

## Round 007: English and symbols

Record DOC-1007; topic: Reference correction.

The fictional review retains café, café, résumé, jalapeño, and déjà vu exactly as written. A status may contain 📄, 🔎, or ✅ without changing the record identifier. The family 👩‍👩‍👧‍👦 and developer 👩🏽‍💻 contain multiple code points. Literal strings <|endoftext|> and <|fim_prefix|> remain ordinary document content.

## Round 008: Hindi

Record DOC-1008; topic: Calculation review.

यह काल्पनिक समीक्षा रिकॉर्ड उपलब्ध प्रमाण और अधूरी जानकारी को अलग रखता है। समीक्षक मूल दस्तावेज़, संशोधन की तारीख और अगले उत्तरदायी व्यक्ति का नाम दर्ज करता है। यदि कोई संलग्नक अनुपलब्ध है तो उसका अनुमान नहीं लगाया जाता। मूल पाठ और उसका क्रम सुरक्षित रहना चाहिए।

## Round 009: Chinese

Record DOC-1009; topic: Access verification.

这份虚构记录说明了审阅过程中的证据和假设。审阅者先确认文档编号，再比较修改记录，并保留需要进一步说明的问题。缺少附件并不等于已有证据相互矛盾。即使分块边界出现在两个段落之间，原始文本也必须能够完整还原。

## Round 010: Japanese

Record DOC-1010; topic: Terminology alignment.

この架空の記録では、確認できた事実と今後確認する必要がある内容を区別します。担当者は文書番号、改訂日、根拠となる資料を記録します。不足している情報を推測で補わず、次の担当者が同じ文脈を理解できるようにします。元の文字列を変更しないことが重要です。

## Round 011: Arabic

Record DOC-1011; topic: Scope boundary.

يحفظ هذا السجل الخيالي الفرق بين الملاحظة والتفسير. يتحقق المراجع من رقم المستند وتاريخ المراجعة والمواد الداعمة قبل تسجيل القرار. إذا كان أحد المرفقات مفقودا، يكتب سؤالا محددا بدلا من افتراض محتواه. يجب أن يبقى النص الأصلي وترتيب الفقرات محفوظين عند تقسيم المستند.

## Round 012: French

Record DOC-1012; topic: Correction history.

Le café conserve un résumé de chaque révision fictive. Une comparaison naïve ne doit pas confondre une observation vérifiée avec une interprétation provisoire. L'équipe précise quelle pièce manque et qui doit répondre. Les formes café et café peuvent sembler identiques tout en contenant des suites de points de code différentes.

## Round 013: German

Record DOC-1013; topic: Page attribution.

Die fiktive Prüfstelle in der Straße bewahrt die ursprüngliche Begründung auf. Änderungen am Titel ersetzen weder die Dokumentkennung noch den Nachweis einer Entscheidung. Die zuständige Person beschreibt, welche Unterlagen fehlen und welche Aussage bereits überprüft wurde. Wörter, Umlaute und Absatzreihenfolge bleiben unverändert.

## Round 014: English and symbols

Record DOC-1014; topic: Review deadline.

The fictional review retains café, café, résumé, jalapeño, and déjà vu exactly as written. A status may contain 📄, 🔎, or ✅ without changing the record identifier. The family 👩‍👩‍👧‍👦 and developer 👩🏽‍💻 contain multiple code points. Literal strings <|endoftext|> and <|fim_prefix|> remain ordinary document content.

## Round 015: Hindi

Record DOC-1015; topic: Collection mapping.

यह काल्पनिक समीक्षा रिकॉर्ड उपलब्ध प्रमाण और अधूरी जानकारी को अलग रखता है। समीक्षक मूल दस्तावेज़, संशोधन की तारीख और अगले उत्तरदायी व्यक्ति का नाम दर्ज करता है। यदि कोई संलग्नक अनुपलब्ध है तो उसका अनुमान नहीं लगाया जाता। मूल पाठ और उसका क्रम सुरक्षित रहना चाहिए।

## Round 016: Chinese

Record DOC-1016; topic: Alternative interpretation.

这份虚构记录说明了审阅过程中的证据和假设。审阅者先确认文档编号，再比较修改记录，并保留需要进一步说明的问题。缺少附件并不等于已有证据相互矛盾。即使分块边界出现在两个段落之间，原始文本也必须能够完整还原。

## Round 017: Japanese

Record DOC-1017; topic: Notification clarity.

この架空の記録では、確認できた事実と今後確認する必要がある内容を区別します。担当者は文書番号、改訂日、根拠となる資料を記録します。不足している情報を推測で補わず、次の担当者が同じ文脈を理解できるようにします。元の文字列を変更しないことが重要です。

## Round 018: Arabic

Record DOC-1018; topic: Archive continuity.

يحفظ هذا السجل الخيالي الفرق بين الملاحظة والتفسير. يتحقق المراجع من رقم المستند وتاريخ المراجعة والمواد الداعمة قبل تسجيل القرار. إذا كان أحد المرفقات مفقودا، يكتب سؤالا محددا بدلا من افتراض محتواه. يجب أن يبقى النص الأصلي وترتيب الفقرات محفوظين عند تقسيم المستند.

## Round 019: French

Record DOC-1019; topic: Readable export.

Le café conserve un résumé de chaque révision fictive. Une comparaison naïve ne doit pas confondre une observation vérifiée avec une interprétation provisoire. L'équipe précise quelle pièce manque et qui doit répondre. Les formes café et café peuvent sembler identiques tout en contenant des suites de points de code différentes.

## Round 020: German

Record DOC-1020; topic: Final reconciliation.

Die fiktive Prüfstelle in der Straße bewahrt die ursprüngliche Begründung auf. Änderungen am Titel ersetzen weder die Dokumentkennung noch den Nachweis einer Entscheidung. Die zuständige Person beschreibt, welche Unterlagen fehlen und welche Aussage bereits überprüft wurde. Wörter, Umlaute und Absatzreihenfolge bleiben unverändert.

## Round 021: English and symbols

Record DOC-1021; topic: Revision identity.

The fictional review retains café, café, résumé, jalapeño, and déjà vu exactly as written. A status may contain 📄, 🔎, or ✅ without changing the record identifier. The family 👩‍👩‍👧‍👦 and developer 👩🏽‍💻 contain multiple code points. Literal strings <|endoftext|> and <|fim_prefix|> remain ordinary document content.

## Round 022: Hindi

Record DOC-1022; topic: Attachment recovery.

यह काल्पनिक समीक्षा रिकॉर्ड उपलब्ध प्रमाण और अधूरी जानकारी को अलग रखता है। समीक्षक मूल दस्तावेज़, संशोधन की तारीख और अगले उत्तरदायी व्यक्ति का नाम दर्ज करता है। यदि कोई संलग्नक अनुपलब्ध है तो उसका अनुमान नहीं लगाया जाता। मूल पाठ और उसका क्रम सुरक्षित रहना चाहिए।

## Round 023: Chinese

Record DOC-1023; topic: Ownership handoff.

这份虚构记录说明了审阅过程中的证据和假设。审阅者先确认文档编号，再比较修改记录，并保留需要进一步说明的问题。缺少附件并不等于已有证据相互矛盾。即使分块边界出现在两个段落之间，原始文本也必须能够完整还原。

## Round 024: Japanese

Record DOC-1024; topic: Claim qualification.

この架空の記録では、確認できた事実と今後確認する必要がある内容を区別します。担当者は文書番号、改訂日、根拠となる資料を記録します。不足している情報を推測で補わず、次の担当者が同じ文脈を理解できるようにします。元の文字列を変更しないことが重要です。

## Round 025: Arabic

Record DOC-1025; topic: Duplicate detection.

يحفظ هذا السجل الخيالي الفرق بين الملاحظة والتفسير. يتحقق المراجع من رقم المستند وتاريخ المراجعة والمواد الداعمة قبل تسجيل القرار. إذا كان أحد المرفقات مفقودا، يكتب سؤالا محددا بدلا من افتراض محتواه. يجب أن يبقى النص الأصلي وترتيب الفقرات محفوظين عند تقسيم المستند.

## Round 026: French

Record DOC-1026; topic: Publication readiness.

Le café conserve un résumé de chaque révision fictive. Une comparaison naïve ne doit pas confondre une observation vérifiée avec une interprétation provisoire. L'équipe précise quelle pièce manque et qui doit répondre. Les formes café et café peuvent sembler identiques tout en contenant des suites de points de code différentes.

## Round 027: German

Record DOC-1027; topic: Reference correction.

Die fiktive Prüfstelle in der Straße bewahrt die ursprüngliche Begründung auf. Änderungen am Titel ersetzen weder die Dokumentkennung noch den Nachweis einer Entscheidung. Die zuständige Person beschreibt, welche Unterlagen fehlen und welche Aussage bereits überprüft wurde. Wörter, Umlaute und Absatzreihenfolge bleiben unverändert.

## Round 028: English and symbols

Record DOC-1028; topic: Calculation review.

The fictional review retains café, café, résumé, jalapeño, and déjà vu exactly as written. A status may contain 📄, 🔎, or ✅ without changing the record identifier. The family 👩‍👩‍👧‍👦 and developer 👩🏽‍💻 contain multiple code points. Literal strings <|endoftext|> and <|fim_prefix|> remain ordinary document content.
