from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus, urlparse


SOURCE_TIERS: dict[str, str] = {
    "al_wasat": "Tier 1",
    "libya_observer": "Tier 1",
    "libya_al_ahrar": "Tier 1",
    "ean_libya": "Tier 1",
    "al_menassa": "Tier 1",
    "lana": "Tier 1",
    "libya_24": "Tier 1",
    "libya_herald": "Tier 1",
    "rna_reportage": "Tier 1",
    "al_sabaah": "Tier 1",
    "libya_review": "Tier 2",
    "address_libya": "Tier 2",
    "al_shahed": "Tier 2",
    "al_marsad": "Tier 2",
    "libya_update": "Tier 2",
    "fawasel_media": "Tier 2",
    "tanasuh": "Tier 2",
    "akhbar_libya_24": "Tier 2",
    "reuters": "Tier 3",
    "ap": "Tier 3",
    "bbc": "Tier 3",
    "al_jazeera_ar_libya": "Tier 3",
    "new_arab": "Tier 3",
    "asharq_al_awsat": "Tier 3",
    "anadolu_agency": "Tier 3",
    "ch_aviation": "Tier 3",
    "ansa": "Tier 3",
    "the_guardian": "Tier 3",
    "bss_news": "Tier 3",
    "volcanodiscovery": "Tier 3",
    "al_ain": "Tier 3",
    "arabi21": "Tier 3",
    "al_mashhad": "Tier 3",
}


PRIORITY_SOURCE_IDS = [
    "al_wasat",
    "libya_observer",
    "libya_al_ahrar",
    "ean_libya",
    "al_menassa",
    "lana",
    "libya_24",
    "libya_herald",
    "rna_reportage",
    "al_sabaah",
    "libya_review",
    "address_libya",
    "al_shahed",
    "al_marsad",
    "libya_update",
    "fawasel_media",
    "tanasuh",
    "akhbar_libya_24",
]


MONITORING_KEYWORDS_AR = [
    "ليبيا",
    "طرابلس",
    "بنغازي",
    "مصراتة",
    "سبها",
    "درنة",
    "الزاوية",
    "الكفرة",
    "فزان",
    "رأس لانوف",
    "البعثة الأممية",
    "الأمم المتحدة",
    "تيتيه",
    "خوري",
    "الحوار المهيكل",
    "مجلس النواب",
    "المجلس الأعلى للدولة",
    "حكومة الوحدة",
    "الدبيبة",
    "حفتر",
    "عقيلة صالح",
    "المنفي",
    "انتخابات",
    "المفوضية الوطنية العليا للانتخابات",
    "أمن",
    "اشتباكات",
    "هجرة",
    "مهاجرين",
    "خفر السواحل",
    "اقتصاد",
    "مصرف ليبيا المركزي",
    "المؤسسة الوطنية للنفط",
    "النفط",
    "الوقود",
    "الكهرباء",
    "ديوان المحاسبة",
    "النائب العام",
    "هيئة مكافحة الفساد",
    "البلديات",
    "إعادة الإعمار",
    "الصحة",
    "حقوق الإنسان",
]


MONITORING_KEYWORDS_EN = [
    "Libya",
    "Libyan",
    "Tripoli",
    "Benghazi",
    "Misrata",
    "Sebha",
    "Derna",
    "Zawiya",
    "Kufra",
    "Fezzan",
    "Ras Lanuf",
    "UNSMIL",
    "United Nations",
    "Tetteh",
    "Koury",
    "structured dialogue",
    "House of Representatives",
    "High State Council",
    "GNU",
    "Dbeibah",
    "Haftar",
    "Aguila Saleh",
    "Presidential Council",
    "elections",
    "HNEC",
    "security",
    "clashes",
    "migration",
    "migrants",
    "Coast Guard",
    "economy",
    "Central Bank of Libya",
    "National Oil Corporation",
    "oil",
    "fuel",
    "electricity",
    "Audit Bureau",
    "Attorney General",
    "Anti-Corruption",
    "municipalities",
    "reconstruction",
    "health",
    "human rights",
]


CATEGORY_SEARCH_TERMS: dict[str, list[str]] = {
    "United Nations": ["UNSMIL", "Tetteh", "Koury", "البعثة الأممية", "الأمم المتحدة", "تيتيه", "خوري"],
    "Politics": ["structured dialogue", "elections", "House of Representatives", "High State Council", "حوار", "انتخابات", "مجلس النواب", "المجلس الأعلى للدولة"],
    "Structured Dialogue": ["structured dialogue", "dialogue committee", "political roadmap", "الحوار المهيكل", "لجنة الحوار", "خارطة الطريق"],
    "Government Affairs": ["GNU", "Dbeibah", "Presidential Council", "Menfi", "government", "حكومة الوحدة", "الدبيبة", "المجلس الرئاسي", "المنفي"],
    "Elections": ["elections", "HNEC", "electoral laws", "انتخابات", "المفوضية الوطنية العليا للانتخابات", "القوانين الانتخابية"],
    "Military & Security": ["security", "clashes", "Zawiya", "Kufra", "أمن", "اشتباكات", "الزاوية", "الكفرة"],
    "Migration": ["migration", "migrants", "UNHCR", "IOM", "deportation", "trafficking", "هجرة", "مهاجرين", "لاجئين", "ترحيل", "اتجار بالبشر"],
    "Human Rights": ["human rights", "rights violations", "detention", "حقوق الإنسان", "انتهاكات", "احتجاز"],
    "Rule of Law": ["Attorney General", "Audit Bureau", "Anti-Corruption", "prosecution", "النائب العام", "ديوان المحاسبة", "مكافحة الفساد", "النيابة"],
    "Central Bank": ["Central Bank", "CBL", "liquidity", "salary", "مصرف ليبيا المركزي", "السيولة", "المرتبات"],
    "Oil": ["NOC", "National Oil Corporation", "oil", "Ras Lanuf", "المؤسسة الوطنية للنفط", "النفط", "رأس لانوف"],
    "Energy": ["fuel", "Brega", "gas", "energy", "الوقود", "البريقة", "الغاز", "الطاقة"],
    "Electricity": ["electricity", "power grid", "GECOL", "الكهرباء", "الشبكة العامة", "الشركة العامة للكهرباء"],
    "Reconstruction": ["reconstruction", "Derna", "development projects", "إعادة الإعمار", "درنة", "مشروعات التنمية"],
    "Economy": ["Central Bank", "NOC", "oil", "fuel", "electricity", "Audit Bureau", "مصرف ليبيا المركزي", "المؤسسة الوطنية للنفط", "النفط", "الوقود", "الكهرباء", "ديوان المحاسبة"],
    "Environment": ["environment", "weather", "floods", "climate", "water", "groundwater", "livestock", "بيئة", "طقس", "فيضانات", "مناخ", "مياه", "مياه جوفية", "الثروة الحيوانية"],
    "Regional Diplomacy": ["regional diplomacy", "Tunisia", "Egypt", "Italy", "France", "Uganda", "تونس", "مصر", "إيطاليا", "فرنسا", "أوغندا"],
    "Regional & International": ["Reuters Libya", "Anadolu Libya", "international Libya", "ليبيا دولي", "ليبيا إقليمي"],
    "Analysis": ["analysis", "commentary", "opinion", "تحليل", "تعليق"],
    "Opinion": ["opinion", "column", "commentary", "رأي", "مقال"],
    "Features": ["feature", "interview", "podcast", "long-form", "تقرير", "مقابلة", "بودكاست"],
    "Varieties": ["sports Libya", "culture Libya", "analysis Libya", "opinion Libya", "رياضة ليبيا", "ثقافة ليبيا", "تحليل ليبيا", "رأي ليبيا"],
}

MANDATORY_PICS_SECTIONS = [
    "United Nations",
    "Politics",
    "Military & Security",
    "Human Rights & Rule of Law",
    "Economy & Energy",
    "Environment",
    "Regional & International",
    "Varieties",
]

SECTION_DEEP_SEARCH_TERMS: dict[str, list[str]] = {
    "United Nations": [
        "UNSMIL Libya",
        "Tetteh Libya",
        "Security Council Libya",
        "UN Libya roadmap",
        "البعثة الأممية ليبيا",
        "تيتيه ليبيا",
        "مجلس الأمن ليبيا",
    ],
    "Politics": [
        "structured dialogue reaction",
        "structured dialogue criticism",
        "structured dialogue support",
        "constitutional objection Libya",
        "executive authority proposal Libya",
        "Central Region social council Libya",
        "Tarhuna central region",
        "Bani Walid central region",
        "Hamada al-Hamra Libya",
        "Naker Libya",
        "Hassadi Libya",
        "Orafi Libya",
        "الحوار المهيكل ردود",
        "انتقادات الحوار المهيكل",
        "دعم مخرجات الحوار",
        "اعتراض دستوري ليبيا",
        "السلطة التنفيذية مقترح",
        "إقليم الوسطى ترهونة",
        "بني وليد إقليم الوسطى",
        "المجلس الاجتماعي إقليم الوسطى",
    ],
    "Military & Security": [
        "Libya arrests",
        "Libya armed clashes",
        "Libya smuggling",
        "Libya drug trafficking",
        "Libya antiquities trafficking",
        "Libya cybercrime",
        "Libya murder case",
        "Libya money smuggling",
        "Libya border incident",
        "Libya military training",
        "southern security Libya",
        "ضبط ليبيا",
        "اشتباكات ليبيا",
        "تهريب ليبيا",
        "مخدرات ليبيا",
        "اتجار بالآثار ليبيا",
        "جريمة قتل ليبيا",
        "تهريب أموال ليبيا",
        "أمن الجنوب ليبيا",
    ],
    "Human Rights & Rule of Law": [
        "Libya migrant smuggling",
        "Libya human trafficking",
        "Libya unidentified bodies",
        "Libya Public Prosecution",
        "Libya corruption",
        "Libya embezzlement",
        "Libya forgery",
        "Derna victims",
        "Libya detention",
        "children armed activities Libya",
        "تهريب مهاجرين ليبيا",
        "اتجار بالبشر ليبيا",
        "جثث مجهولة ليبيا",
        "النائب العام ليبيا",
        "فساد ليبيا",
        "اختلاس ليبيا",
        "تزوير ليبيا",
        "ضحايا درنة",
    ],
    "Economy & Energy": [
        "Libya oil production",
        "AGOCO Libya",
        "Sirte Oil Libya",
        "SLB Libya",
        "PETEX Libya",
        "Libya fuel",
        "Libya electricity",
        "Libya ports",
        "Libya reconstruction",
        "Libya infrastructure",
        "Libya exchange rate",
        "Libya digital payments",
        "Libya free zones",
        "Libya export development",
        "إنتاج النفط ليبيا",
        "الخليج العربي للنفط",
        "شركة سرت للنفط",
        "الوقود ليبيا",
        "الكهرباء ليبيا",
        "الموانئ ليبيا",
        "إعادة الإعمار ليبيا",
        "سعر الصرف ليبيا",
        "المدفوعات الرقمية ليبيا",
        "المناطق الحرة ليبيا",
    ],
    "Environment": [
        "Libya rain",
        "Libya floods",
        "Libya water resources",
        "Libya groundwater",
        "Libya pollution",
        "Libya poisonous fish",
        "Libya insects",
        "Libya pests",
        "Libya climate",
        "Libya agricultural damage",
        "أمطار ليبيا",
        "فيضانات ليبيا",
        "المياه الجوفية ليبيا",
        "تلوث ليبيا",
        "أسماك سامة ليبيا",
        "حشرات ليبيا",
        "آفات ليبيا",
        "مناخ ليبيا",
        "أضرار زراعية ليبيا",
    ],
    "Regional & International": [
        "Libya Egypt talks",
        "Libya Italy talks",
        "Libya Tunisia border",
        "Libya Turkey agreement",
        "EU Libya migration",
        "US Libya elections",
        "African Union Libya",
        "مصر ليبيا",
        "إيطاليا ليبيا",
        "تونس ليبيا",
        "تركيا ليبيا",
        "الاتحاد الأوروبي ليبيا",
        "الاتحاد الأفريقي ليبيا",
    ],
    "Varieties": [
        "Libya analysis",
        "Libya opinion",
        "Libya feature",
        "Libya podcast",
        "Libya interview",
        "Libya think tank",
        "تحليل ليبيا",
        "رأي ليبيا",
        "مقال ليبيا",
        "مقابلة ليبيا",
        "بودكاست ليبيا",
    ],
}

SECTION_RECOVERY_SOURCE_IDS: dict[str, list[str]] = {
    "Military & Security": ["al_wasat", "rna_reportage", "al_marsad", "libya_al_ahrar", "libya_observer", "libya_review", "address_libya"],
    "Human Rights & Rule of Law": ["al_wasat", "rna_reportage", "al_marsad", "libya_review", "libya_al_ahrar", "libya_observer", "address_libya"],
    "Economy & Energy": ["al_wasat", "ean_libya", "libya_observer", "libya_review", "libya_update", "address_libya", "libya_herald"],
    "Environment": ["al_wasat", "ean_libya", "rna_reportage", "libya_24", "al_sabaah", "volcanodiscovery"],
    "Politics": ["al_wasat", "libya_observer", "ean_libya", "libya_al_ahrar", "al_menassa", "libya_review", "akhbar_libya_24", "al_marsad"],
    "Varieties": ["al_wasat", "new_arab", "asharq_al_awsat", "libya_review", "arabi21", "al_jazeera_ar_libya"],
}

CONTEXTUAL_EXPANSION_DIMENSIONS: dict[str, list[str]] = {
    "event": ["latest", "update", "development", "تطور", "آخر", "مستجدات"],
    "reaction": ["reaction", "response", "statement", "رد", "تعليق", "تصريح", "بيان"],
    "support": ["support", "welcomes", "backs", "دعم", "ترحيب", "يؤيد", "مساندة"],
    "opposition": ["opposition", "rejection", "criticism", "criticizes", "رفض", "انتقاد", "يعترض", "مخاوف"],
    "objection": ["objection", "legal concern", "constitutional concern", "اعتراض", "مخاوف قانونية", "مخاوف دستورية"],
    "implementation": ["implementation", "implementation concerns", "obstacles", "تنفيذ", "مخاوف التنفيذ", "عقبات"],
    "analysis": ["analysis", "commentary", "opinion", "feature", "تحليل", "رأي", "مقال", "قراءة"],
    "commentary": ["podcast", "interview", "discussion", "editorial", "بودكاست", "مقابلة", "نقاش", "افتتاحية"],
}

ACTOR_DISCOVERY_TERMS: dict[str, list[str]] = {
    "government_actors": ["government", "minister", "cabinet", "GNU", "حكومة", "وزير", "مجلس الوزراء"],
    "political_actors": ["MP", "parliament", "HCS", "party", "مجلس النواب", "المجلس الأعلى للدولة", "نائب", "حزب"],
    "municipal_actors": ["municipality", "mayor", "municipal council", "بلدية", "عميد", "المجلس البلدي"],
    "tribal_actors": ["tribal council", "social council", "notables", "مجلس اجتماعي", "قبائل", "أعيان"],
    "international_actors": ["EU", "US", "Italy", "Egypt", "foreign ministry", "الاتحاد الأوروبي", "الولايات المتحدة", "إيطاليا", "مصر", "الخارجية"],
    "un_actors": ["UNSMIL", "UN", "Tetteh", "UNHCR", "IOM", "البعثة الأممية", "الأمم المتحدة", "تيتيه", "مفوضية اللاجئين"],
    "civil_society_actors": ["civil society", "activists", "rights groups", "journalists", "المجتمع المدني", "نشطاء", "منظمات حقوقية", "صحفيون"],
}

PRIMARY_THEME_SEARCH_TERMS: dict[str, list[str]] = {
    "Structured Dialogue": [
        "structured dialogue",
        "dialogue recommendations",
        "executive authority proposals",
        "constitutional basis",
        "economic track",
        "الحوار المهيكل",
        "مخرجات الحوار",
        "السلطة التنفيذية",
        "المسار الدستوري",
        "المسار الاقتصادي",
    ],
    "Elections": ["elections", "electoral laws", "HNEC", "انتخابات", "القوانين الانتخابية", "المفوضية"],
    "Central Region": [
        "central region",
        "regional division",
        "municipalities central region",
        "الإقليم الأوسط",
        "إقليم الوسطى",
        "المنطقة الوسطى",
        "البلديات",
        "المجالس الاجتماعية",
    ],
    "Migration": [
        "migration",
        "migrant settlement",
        "deportation",
        "foreign labor",
        "UNHCR",
        "IOM",
        "هجرة",
        "توطين المهاجرين",
        "ترحيل",
        "العمالة الأجنبية",
        "مفوضية اللاجئين",
        "المنظمة الدولية للهجرة",
    ],
    "UNSMIL": ["UNSMIL", "Tetteh", "Security Council Libya", "البعثة الأممية", "تيتيه", "مجلس الأمن ليبيا"],
    "Central Bank": [
        "Central Bank of Libya",
        "CBL",
        "liquidity",
        "salary bill",
        "exchange rate",
        "مصرف ليبيا المركزي",
        "السيولة",
        "المرتبات",
        "سعر الصرف",
    ],
    "NOC": [
        "National Oil Corporation",
        "NOC",
        "oil production",
        "fuel crisis",
        "AGOCO",
        "GECOL electricity",
        "electricity outages",
        "المؤسسة الوطنية للنفط",
        "إنتاج النفط",
        "أزمة الوقود",
        "الخليج العربي للنفط",
        "الكهرباء",
    ],
    "AGOCO": ["AGOCO Libya", "Arabian Gulf Oil Company", "الخليج العربي للنفط"],
    "Electricity": ["Libya electricity", "GECOL Libya", "power outages Libya", "الكهرباء ليبيا", "الشركة العامة للكهرباء"],
    "Judiciary": ["Libya judiciary", "Public Prosecution Libya", "court rulings Libya", "القضاء ليبيا", "النائب العام ليبيا", "أحكام قضائية ليبيا"],
    "Prison Conditions": ["Libya prison conditions", "detention Libya", "prisoners Libya", "أوضاع السجون ليبيا", "احتجاز ليبيا", "سجناء ليبيا"],
    "Libya-Togo": ["Libya Togo", "Dbeibah Baour", "Togolese foreign minister Libya", "African Union Libya Togo", "ليبيا توغو", "الدبيبة باعور"],
    "Libya-Oman": ["Libya Oman", "Omani Libya", "ليبيا عمان", "العماني ليبيا"],
    "Macron-Saddam": ["Macron Saddam Haftar", "French Embassy Saddam Haftar", "France Libya Haftar", "ماكرون صدام حفتر", "فرنسا صدام حفتر"],
    "Zawiya Clashes": ["Zawiya clashes", "armed groups Zawiya", "security Zawiya", "اشتباكات الزاوية", "مسلحو الزاوية"],
    "Constitutional Issues": ["constitutional basis", "constitutional track", "الدستورية", "المسار الدستوري", "القاعدة الدستورية"],
    "Executive Authority": ["executive authority", "new government", "parallel government", "السلطة التنفيذية", "حكومة جديدة", "حكومة موازية"],
}

MANDATORY_EXPANSION_THEMES = [
    "Analysis",
    "Structured Dialogue",
    "Migration",
    "Elections",
    "Central Region",
    "Libya-Togo",
    "Libya-Oman",
    "Macron-Saddam",
    "NOC",
    "AGOCO",
    "Electricity",
    "Judiciary",
    "Prison Conditions",
]

ANALYSIS_DISCOVERY_TERMS = [
    "Libya analysis",
    "Libya opinion",
    "Libya commentary",
    "Libya editorial",
    "Libya feature",
    "Libya podcast",
    "Libya interview",
    "Libya long-form report",
    "Libya think tank",
    "Global Finance Libya",
    "Africa Intelligence Libya",
    "Independent Arabia Libya",
    "Drooj Libya",
    "Global Initiative Libya",
    "تحليل ليبيا",
    "رأي ليبيا",
    "مقال ليبيا",
    "افتتاحية ليبيا",
    "بودكاست ليبيا",
    "مقابلة ليبيا",
    "تقرير مطول ليبيا",
]

RULE_OF_LAW_HARVEST_TERMS = [
    "Libya Public Prosecution",
    "Libya corruption",
    "Libya embezzlement",
    "Libya forgery",
    "Libya murder",
    "Libya robbery",
    "Libya drug trafficking",
    "Libya human trafficking",
    "Libya migrant bodies",
    "Libya detention",
    "Libya court rulings",
    "النائب العام ليبيا",
    "فساد ليبيا",
    "اختلاس ليبيا",
    "تزوير ليبيا",
    "قتل ليبيا",
    "سرقة ليبيا",
    "مخدرات ليبيا",
    "اتجار بالبشر ليبيا",
    "جثث مهاجرين ليبيا",
    "احتجاز ليبيا",
    "أحكام قضائية ليبيا",
]

PERSON_EXPANSION_TERMS: dict[str, list[str]] = {
    "Structured Dialogue": [
        "Nassiya structured dialogue",
        "Awjali structured dialogue",
        "Orafi structured dialogue",
        "Shaibani structured dialogue",
        "Takala structured dialogue",
        "Omran structured dialogue",
        "Soul structured dialogue",
        "Bin Taboun structured dialogue",
        "Birah structured dialogue",
        "Bou Dawara structured dialogue",
        "Bu Brik structured dialogue",
        "نصية الحوار المهيكل",
        "العوجلي الحوار المهيكل",
        "العريفي الحوار المهيكل",
        "الشيباني الحوار المهيكل",
        "تكالة الحوار المهيكل",
        "عمران الحوار المهيكل",
        "صول الحوار المهيكل",
        "بن طابون الحوار المهيكل",
        "بيرة الحوار المهيكل",
        "بو دوارة الحوار المهيكل",
        "بو بريك الحوار المهيكل",
    ],
    "Macron-Saddam": [
        "Macron Saddam Haftar",
        "Saddam Haftar French statements",
        "French Embassy Libya Saddam Haftar",
        "ماكرون صدام حفتر",
        "السفارة الفرنسية صدام حفتر",
    ],
    "Libya-Togo": [
        "Dbeibah Baour",
        "Togolese FM Libya",
        "African Union Libya Togo",
        "الدبيبة باعور",
        "وزير خارجية توغو ليبيا",
        "الاتحاد الأفريقي ليبيا توغو",
    ],
}

THINK_TANK_DISCOVERY_TERMS = [
    "CFR Libya",
    "ICG Libya",
    "ECFR Libya",
    "Chatham House Libya",
    "Carnegie Libya",
    "MEI Libya",
    "Brookings Libya",
    "Atlantic Council Libya",
    "ISPI Libya",
    "Arab Center Libya",
]

CONTEXTUAL_SOURCE_IDS = {
    "al_wasat",
    "libya_observer",
    "libya_al_ahrar",
    "ean_libya",
    "al_menassa",
    "lana",
    "libya_24",
    "libya_herald",
    "rna_reportage",
    "al_sabaah",
    "libya_review",
    "address_libya",
    "al_shahed",
    "al_marsad",
    "libya_update",
    "fawasel_media",
    "tanasuh",
    "akhbar_libya_24",
    "asharq_al_awsat",
    "al_jazeera_ar_libya",
    "new_arab",
    "arabi21",
    "al_ain",
    "anadolu_agency",
    "reuters",
    "ap",
    "bbc",
}

MANDATORY_CONTEXT_SOURCE_IDS = [
    "libya_observer",
    "al_wasat",
    "ean_libya",
    "libya_al_ahrar",
    "al_menassa",
    "libya_review",
    "libya_update",
    "address_libya",
    "libya_24",
    "lana",
    "al_sabaah",
    "asharq_al_awsat",
    "new_arab",
    "al_jazeera_ar_libya",
    "anadolu_agency",
    "reuters",
    "ap",
    "bbc",
]

ANALYSIS_CONTEXT_SOURCE_IDS = {
    "asharq_al_awsat",
    "new_arab",
    "al_jazeera_ar_libya",
    "arabi21",
    "al_ain",
    "ap",
    "bbc",
}


SOURCE_URLS: dict[str, dict[str, list[str]]] = {
    "al_wasat": {
        "collection_urls": [
            "https://alwasat.ly/section/libya",
        ],
        "search_url_templates": [],
    },
    "ean_libya": {
        "collection_urls": ["https://www.eanlibya.com/", "https://www.eanlibya.com/category/news/"],
        "search_url_templates": ["https://www.eanlibya.com/?s={query}"],
    },
    "rna_reportage": {
        "collection_urls": ["https://reportage.ly/", "https://reportage.ly/category/news/"],
        "search_url_templates": ["https://reportage.ly/?s={query}"],
    },
    "libya_observer": {
        "collection_urls": [
            "https://libyaobserver.ly/news",
            "https://libyaobserver.ly/inbrief",
            "https://libyaobserver.ly/economy",
        ],
        "search_url_templates": [],
    },
    "libya_review": {
        "collection_urls": ["https://libyareview.com/category/libya/", "https://libyareview.com/"],
        "search_url_templates": ["https://libyareview.com/?s={query}"],
    },
    "lana": {
        "collection_urls": [
            "https://lana.gov.ly/category.php?lang=ar&id=8",
            "https://lana.gov.ly/",
        ],
        "search_url_templates": [
            "https://lana.gov.ly/search.php?lang=ar&q={query}",
            "https://lana.gov.ly/?s={query}",
        ],
    },
    "al_marsad": {
        "collection_urls": ["https://almarsad.co/category/libya/", "https://almarsad.co/"],
        "search_url_templates": ["https://almarsad.co/?s={query}"],
    },
    "al_shahed": {
        "collection_urls": ["https://lywitness.com/category/libya/", "https://lywitness.com/"],
        "search_url_templates": ["https://lywitness.com/?s={query}"],
    },
    "libya_24": {
        "collection_urls": ["https://libya24.tv/category/news/", "https://libya24.tv/"],
        "search_url_templates": ["https://libya24.tv/?s={query}"],
    },
    "al_saaa_24": {
        "collection_urls": ["https://alsaaa24.net/category/libya/", "https://alsaaa24.net/"],
        "search_url_templates": ["https://alsaaa24.net/?s={query}"],
    },
    "address_libya": {
        "collection_urls": ["https://www.addresslibya.com/category/libya/", "https://www.addresslibya.com/"],
        "search_url_templates": ["https://www.addresslibya.com/?s={query}"],
    },
    "asharq_al_awsat": {
        "collection_urls": ["https://aawsat.com/tags/%D9%84%D9%8A%D8%A8%D9%8A%D8%A7"],
        "search_url_templates": ["https://aawsat.com/search?search={query}"],
    },
    "fawasel_media": {
        "collection_urls": ["https://fawaselmedia.com/category/news/", "https://fawaselmedia.com/"],
        "search_url_templates": ["https://fawaselmedia.com/?s={query}"],
    },
    "tanasuh": {
        "collection_urls": ["https://tanasuh.tv/category/news/", "https://tanasuh.tv/"],
        "search_url_templates": ["https://tanasuh.tv/?s={query}"],
    },
    "libya_herald": {
        "collection_urls": ["https://libyaherald.com/category/libya/", "https://libyaherald.com/"],
        "search_url_templates": ["https://libyaherald.com/?s={query}"],
    },
    "al_menassa": {
        "collection_urls": ["https://almenassa.ly/wide-web-1/", "https://almenassa.ly/"],
        "search_url_templates": ["https://almenassa.ly/?s={query}"],
    },
    "al_mashhad": {
        "collection_urls": ["https://www.almashhad.com/section/773112298002792-News/"],
        "search_url_templates": ["https://www.almashhad.com/search?keyword={query}"],
    },
    "libya_al_ahrar": {
        "collection_urls": ["https://libyaalahrar.tv/category/news/"],
        "search_url_templates": ["https://libyaalahrar.tv/?s={query}"],
    },
    "libya_update": {
        "collection_urls": ["https://libyaupdate.com/category/news/", "https://libyaupdate.com/"],
        "search_url_templates": ["https://libyaupdate.com/?s={query}"],
    },
    "akhbar_libya_24": {
        "collection_urls": ["https://akhbarlibya24.net/category/libya-news/", "https://akhbarlibya24.net/"],
        "search_url_templates": ["https://akhbarlibya24.net/?s={query}"],
    },
    "al_sabaah": {
        "collection_urls": ["https://alsabaah.ly/category/libya/", "https://alsabaah.ly/"],
        "search_url_templates": ["https://alsabaah.ly/?s={query}"],
    },
    "al_jazeera_ar_libya": {
        "collection_urls": ["https://www.aljazeera.net/where/mideast/arab/libya/"],
        "search_url_templates": ["https://www.aljazeera.net/search/{query}"],
    },
    "al_ain": {
        "collection_urls": ["https://al-ain.com/tag/libya", "https://al-ain.com/"],
        "search_url_templates": ["https://al-ain.com/search?query={query}"],
    },
    "arabi21": {
        "collection_urls": ["https://arabi21.com/stories/t/49474/0/%D9%84%D9%8A%D8%A8%D9%8A%D8%A7"],
        "search_url_templates": ["https://arabi21.com/Search?searchText={query}"],
    },
    "new_arab": {
        "collection_urls": ["https://www.newarab.com/tag/libya"],
        "search_url_templates": ["https://www.newarab.com/search?search_api_fulltext={query}"],
    },
    "ansa": {
        "collection_urls": ["https://www.ansa.it/english/", "https://www.ansa.it/english/news/world/"],
        "search_url_templates": ["https://www.ansa.it/english/search.html?query={query}"],
    },
    "anadolu_agency": {
        "collection_urls": ["https://www.aa.com.tr/en/africa", "https://www.aa.com.tr/en"],
        "search_url_templates": ["https://www.aa.com.tr/en/search/?s={query}"],
    },
    "the_guardian": {
        "collection_urls": ["https://www.theguardian.com/world/libya"],
        "search_url_templates": ["https://www.theguardian.com/search?q={query}"],
    },
    "bss_news": {
        "collection_urls": ["https://www.bssnews.net/international", "https://www.bssnews.net/"],
        "search_url_templates": ["https://www.bssnews.net/search?q={query}"],
    },
    "ch_aviation": {
        "collection_urls": ["https://www.ch-aviation.com/news"],
        "search_url_templates": ["https://www.ch-aviation.com/news?query={query}"],
    },
    "volcanodiscovery": {
        "collection_urls": ["https://www.volcanodiscovery.com/earthquakes/libya.html"],
        "search_url_templates": ["https://www.volcanodiscovery.com/search.html?q={query}"],
    },
    "reuters": {
        "collection_urls": ["https://www.reuters.com/world/africa/"],
        "search_url_templates": ["https://www.reuters.com/site-search/?query={query}"],
    },
    "ap": {
        "collection_urls": ["https://apnews.com/hub/libya"],
        "search_url_templates": ["https://apnews.com/search?q={query}"],
    },
    "bbc": {
        "collection_urls": ["https://www.bbc.com/news/topics/c302m85qenyt"],
        "search_url_templates": ["https://www.bbc.co.uk/search?q={query}", "https://www.bbc.com/search?q={query}"],
    },
}


def sort_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {source_id: index for index, source_id in enumerate(PRIORITY_SOURCE_IDS)}
    return sorted(sources, key=lambda source: priority.get(source["id"], len(priority)))


def build_collection_urls(
    source: dict[str, Any],
    keywords: list[str],
    start_date: datetime | None,
    end_date: datetime | None = None,
) -> list[str]:
    configured = SOURCE_URLS.get(source["id"], {})
    urls = list(source.get("collection_urls", []))
    urls.extend(configured.get("collection_urls", []))
    urls.append(source["url"])
    urls.extend(recovery_collection_urls(source, start_date, end_date))

    search_keywords = source["search_keywords"] if "search_keywords" in source else default_search_keywords(source, keywords)
    date_tokens = date_search_tokens(start_date, end_date) if source.get("include_date_search_tokens", True) else []
    for template in [*source.get("search_url_templates", []), *configured.get("search_url_templates", [])]:
        for keyword in [*date_tokens, *search_keywords]:
            urls.append(template.format(query=quote_plus(keyword), raw_query=keyword))

    return dedupe(urls)


def build_contextual_expansion_urls(
    source: dict[str, Any],
    primary_themes: list[str],
    max_urls: int = 8,
) -> list[str]:
    configured = SOURCE_URLS.get(source["id"], {})
    templates = [*source.get("search_url_templates", []), *configured.get("search_url_templates", [])]
    if not templates:
        templates = fallback_search_templates(source)
    if source["id"] not in CONTEXTUAL_SOURCE_IDS:
        return []

    themes = dedupe([*primary_themes, *MANDATORY_EXPANSION_THEMES])
    queries_by_theme: list[list[str]] = []
    for theme in themes:
        base_terms = contextual_theme_terms(theme)
        if theme == "Analysis":
            theme_queries = [*ANALYSIS_DISCOVERY_TERMS]
            if source["id"] in ANALYSIS_CONTEXT_SOURCE_IDS:
                theme_queries.extend(THINK_TANK_DISCOVERY_TERMS)
            queries_by_theme.append(dedupe(theme_queries))
            continue
        theme_queries: list[str] = []
        for base_term in base_terms[:3]:
            for dimension_terms in CONTEXTUAL_EXPANSION_DIMENSIONS.values():
                expansion_terms = dimension_terms[:1]
                if source["language"] == "ar" and len(dimension_terms) > 3:
                    expansion_terms.append(dimension_terms[3])
                elif source["language"] != "ar" and len(dimension_terms) > 1:
                    expansion_terms.append(dimension_terms[1])
                for expansion_term in expansion_terms:
                    theme_queries.append(f"{base_term} {expansion_term}")
            for actor_terms in ACTOR_DISCOVERY_TERMS.values():
                actor_term = actor_terms[0 if source["language"] != "ar" else min(4, len(actor_terms) - 1)]
                theme_queries.append(f"{base_term} {actor_term}")
            if source["language"] == "ar":
                theme_queries.extend(f"{base_term} {term}" for term in ["رد", "رفض", "دعم", "تحليل", "رأي", "مقابلة"])
            else:
                theme_queries.extend(f"{base_term} {term}" for term in ["reaction", "criticism", "support", "analysis", "opinion", "interview"])
        theme_queries.extend(PERSON_EXPANSION_TERMS.get(theme, []))
        if theme in {"Human Rights", "Rule of Law", "Judiciary", "Prison Conditions", "Migration"}:
            theme_queries.extend(RULE_OF_LAW_HARVEST_TERMS)
        if theme in {"Analysis", "Structured Dialogue", "Migration", "Elections", "Central Region"}:
            theme_queries.extend(ANALYSIS_DISCOVERY_TERMS)
        queries_by_theme.append(dedupe(theme_queries))

    queries_by_theme.append(language_filtered_queries(source, RULE_OF_LAW_HARVEST_TERMS))
    queries_by_theme.append(language_filtered_queries(source, ANALYSIS_DISCOVERY_TERMS))

    queries: list[str] = []
    max_theme_queries = max((len(theme_queries) for theme_queries in queries_by_theme), default=0)
    for index in range(max_theme_queries):
        for theme_queries in queries_by_theme:
            if index < len(theme_queries):
                queries.append(theme_queries[index])

    urls: list[str] = []
    for template in templates:
        for query in dedupe(queries)[: max_urls * 2]:
            urls.append(template.format(query=quote_plus(query), raw_query=query))
            if len(urls) >= max_urls:
                return dedupe(urls)
    return dedupe(urls)


def language_filtered_queries(source: dict[str, Any], queries: list[str]) -> list[str]:
    if source["language"] == "ar":
        return [query for query in queries if re.search(r"[\u0600-\u06ff]", query)][:12]
    return [query for query in queries if not re.search(r"[\u0600-\u06ff]", query)][:12]


def build_section_coverage_urls(
    source: dict[str, Any],
    section_name: str,
    max_urls: int = 6,
) -> list[str]:
    if source["id"] not in CONTEXTUAL_SOURCE_IDS:
        return []
    preferred_sources = SECTION_RECOVERY_SOURCE_IDS.get(section_name)
    if preferred_sources and source["id"] not in preferred_sources and SOURCE_TIERS.get(source["id"]) != "Tier 1":
        return []
    configured = SOURCE_URLS.get(source["id"], {})
    templates = [*source.get("search_url_templates", []), *configured.get("search_url_templates", [])]
    if not templates:
        templates = fallback_search_templates(source)
    queries = SECTION_DEEP_SEARCH_TERMS.get(section_name, CATEGORY_SEARCH_TERMS.get(section_name, [section_name]))
    urls: list[str] = []
    for template in templates:
        for query in queries:
            urls.append(template.format(query=quote_plus(query), raw_query=query))
            if len(urls) >= max_urls:
                return dedupe(urls)
    return dedupe(urls)


def fallback_search_templates(source: dict[str, Any]) -> list[str]:
    parsed = urlparse(source["url"])
    if not parsed.scheme or not parsed.netloc:
        return []
    base = f"{parsed.scheme}://{parsed.netloc}"
    return [
        f"{base}/?s={{query}}",
        f"{base}/search?q={{query}}",
        f"{base}/search?query={{query}}",
    ]


def contextual_theme_terms(theme: str) -> list[str]:
    if theme in PRIMARY_THEME_SEARCH_TERMS:
        return PRIMARY_THEME_SEARCH_TERMS[theme]
    if theme in CATEGORY_SEARCH_TERMS:
        return CATEGORY_SEARCH_TERMS[theme]
    if theme == "Analysis":
        return ANALYSIS_DISCOVERY_TERMS
    return [theme]


def recovery_collection_urls(source: dict[str, Any], start_date: datetime | None, end_date: datetime | None = None) -> list[str]:
    parsed = urlparse(source["url"])
    if not parsed.scheme or not parsed.netloc:
        return []
    base = f"{parsed.scheme}://{parsed.netloc}"
    urls = [
        f"{base}/feed/",
        f"{base}/rss/",
        f"{base}/rss.xml",
        f"{base}/sitemap.xml",
        f"{base}/news-sitemap.xml",
        f"{base}/sitemap_index.xml",
    ]
    for path in ("libya", "news", "latest", "category/libya", "category/news", "archives"):
        urls.append(f"{base}/{path.strip('/')}/")
    for token in date_path_tokens(start_date, end_date):
        urls.extend(
            [
                f"{base}/{token}/",
                f"{base}/archive/{token}/",
                f"{base}/archives/{token}/",
            ]
        )
    for keyword in default_search_keywords(source, []):
        query = quote_plus(keyword)
        urls.extend(
            [
                f"{base}/?s={query}",
                f"{base}/search?q={query}",
                f"{base}/search?query={query}",
            ]
        )
    return urls


def default_search_keywords(source: dict[str, Any], keywords: list[str]) -> list[str]:
    if source["language"] == "ar":
        defaults = ["ليبيا", "البعثة الأممية", "طرابلس", "بنغازي"]
        monitoring = MONITORING_KEYWORDS_AR
    else:
        defaults = ["Libya", "UNSMIL", "Tripoli", "Benghazi"]
        monitoring = MONITORING_KEYWORDS_EN
    extras = [keyword for keyword in [*monitoring, *keywords] if keyword not in defaults]
    cap = 28 if SOURCE_TIERS.get(source["id"]) == "Tier 1" else 14
    return [*defaults, *extras[:cap]]


def date_search_tokens(start_date: datetime | None, end_date: datetime | None = None) -> list[str]:
    if not start_date:
        return []
    end = end_date or start_date
    if end < start_date:
        end = start_date
    tokens: list[str] = []
    current = start_date
    while current.date() <= end.date():
        day = current.day
        month_ar = ARABIC_MONTHS[current.month - 1]
        month_en = current.strftime("%B")
        tokens.extend(
            [
                current.strftime("%Y/%m"),
                current.strftime("%Y/%m/%d"),
                current.strftime("%Y-%m-%d"),
                current.strftime("%d/%m/%Y"),
                f"{day} {month_en} {current.year}",
                f"{month_en} {day}, {current.year}",
                f"{day} {month_ar} {current.year}",
                f"{day:02d} {month_ar} {current.year}",
                f"نشر بتاريخ: {current.strftime('%d-%m-%Y')}",
            ]
        )
        current += timedelta(days=1)
    return dedupe(tokens)


def date_path_tokens(start_date: datetime | None, end_date: datetime | None = None) -> list[str]:
    if not start_date:
        return []
    end = end_date or start_date
    if end < start_date:
        end = start_date
    tokens: list[str] = []
    current = start_date
    while current.date() <= end.date():
        tokens.extend(
            [
                current.strftime("%Y/%m"),
                current.strftime("%Y/%m/%d"),
                current.strftime("%Y-%m-%d"),
            ]
        )
        current += timedelta(days=1)
    return dedupe(tokens)


ARABIC_MONTHS = [
    "يناير",
    "فبراير",
    "مارس",
    "أبريل",
    "مايو",
    "يونيو",
    "يوليو",
    "أغسطس",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
