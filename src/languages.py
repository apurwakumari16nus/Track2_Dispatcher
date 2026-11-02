"""Job cards in a workshop's own language. Fixed wording, so a card never depends on a model, and the record stays in
English so the dispatcher can always read it. Anything with no translation here simply stays in English.
"""

from __future__ import annotations

NAMES = {"en": "English", "hi": "हिन्दी", "zh": "中文"}
PRODUCTS = {
    "hi": {"Hoodie": "हुडी", "Vest": "वेस्ट", "Scarf": "स्कार्फ", "Beanie": "बीनी", "Cardigan": "कार्डिगन", "Crewneck sweater": "स्वेटर", "Polo shirt": "पोलो शर्ट"},
    "zh": {"Hoodie": "连帽衫", "Vest": "背心", "Scarf": "围巾", "Beanie": "毛线帽", "Cardigan": "开衫", "Crewneck sweater": "圆领毛衣", "Polo shirt": "Polo衫"},
}
WORDS = {
    "hi": {
        "New job from SweaterCo: {order}, {goods}.\nNeeded back by {back}. Rate {rate} per piece, {total} in total.\nCan you take it?":
            "SweaterCo से नया काम: {order}, {goods}।\n{back} तक वापस चाहिए। रेट {rate} प्रति पीस, कुल {total}।\nक्या आप यह ले सकते हैं?",
        "A reminder about {order}, {goods}. Can you take it? We need to plan today.": "{order}, {goods} के बारे में याद दिला रहे हैं। क्या आप यह ले सकते हैं? हमें आज योजना बनानी है।",
        "How is {order} looking? It is booked back on {back}.": "{order} का क्या हाल है? इसकी वापसी {back} को तय है।",
        "Accept": "स्वीकार करें", "Cannot take it": "नहीं ले सकते", "Started": "काम शुरू", "Completed": "पूरा हुआ", "Shipped": "भेज दिया",
        "Report a problem": "समस्या बताएँ", "Back": "वापस", "Will be late": "देर होगी",
        "Why can you not take it?": "आप यह क्यों नहीं ले सकते?", "What is the problem?": "समस्या क्या है?", "How many days late?": "कितने दिन की देरी?",
        "No capacity right now": "अभी क्षमता नहीं है", "Machine or power problem": "मशीन या बिजली की समस्या", "Cannot make this product": "यह उत्पाद नहीं बना सकते",
        "Rate is too low": "रेट बहुत कम है", "Date is too tight": "तारीख बहुत जल्दी है", "Machine down": "मशीन खराब है", "Material short": "सामान कम है", "Quality problem": "गुणवत्ता की समस्या",
        "+{days} day": "+{days} दिन", "+{days} days": "+{days} दिन",
        "Booked, not sent yet": "बुक, अभी भेजा नहीं", "Waiting for the workshop": "आपके जवाब का इंतज़ार", "Accepted": "स्वीकार किया", "In production": "उत्पादन में",
        "On its way back": "वापस आ रहा है", "Received": "प्राप्त हुआ", "Declined by the workshop": "अस्वीकार किया",
        "{order}: {stage}. Thank you, {name}.": "{order}: {stage}। धन्यवाद, {name}।",
        "{order}: declined, reason noted. Thank you, {name}.": "{order}: अस्वीकार किया, कारण दर्ज हुआ। धन्यवाद, {name}।",
        "{order}: completed. Thank you, {name}. You are free for new work now.": "{order}: पूरा हुआ। धन्यवाद, {name}। अब आप नए काम के लिए खाली हैं।",
        "{order}: completed. Thank you, {name}. You have room again: {days} days of work left.": "{order}: पूरा हुआ। धन्यवाद, {name}। अब {days} दिन का काम बाकी है।",
        "{order}: thank you, the team has been told: {reason}.": "{order}: धन्यवाद, टीम को बता दिया गया है: {reason}।",
        "{order}: thank you, the team has been told it is {days} days late.": "{order}: धन्यवाद, टीम को बता दिया गया है कि इसमें {days} दिन की देरी है।",
        "Job cards will now come in English.": "अब जॉब कार्ड हिन्दी में आएँगे।",
    },
    "zh": {
        "New job from SweaterCo: {order}, {goods}.\nNeeded back by {back}. Rate {rate} per piece, {total} in total.\nCan you take it?":
            "SweaterCo 新订单：{order}，{goods}。\n需在 {back} 前返回。单价 {rate}，总计 {total}。\n您能接吗？",
        "A reminder about {order}, {goods}. Can you take it? We need to plan today.": "提醒一下 {order}，{goods}。您能接吗？我们今天需要安排计划。",
        "How is {order} looking? It is booked back on {back}.": "{order} 进展如何？预计 {back} 返回。",
        "Accept": "接受", "Cannot take it": "无法接单", "Started": "已开工", "Completed": "已完成", "Shipped": "已发货",
        "Report a problem": "报告问题", "Back": "返回", "Will be late": "会延迟",
        "Why can you not take it?": "为什么无法接单？", "What is the problem?": "是什么问题？", "How many days late?": "延迟几天？",
        "No capacity right now": "目前没有产能", "Machine or power problem": "机器或电力问题", "Cannot make this product": "无法生产此产品",
        "Rate is too low": "单价太低", "Date is too tight": "交期太紧", "Machine down": "机器故障", "Material short": "材料不足", "Quality problem": "质量问题",
        "+{days} day": "+{days} 天", "+{days} days": "+{days} 天",
        "Booked, not sent yet": "已预订，尚未发出", "Waiting for the workshop": "等待您的回复", "Accepted": "已接受", "In production": "生产中",
        "On its way back": "返回途中", "Received": "已收货", "Declined by the workshop": "已拒绝",
        "{order}: {stage}. Thank you, {name}.": "{order}：{stage}。谢谢，{name}。",
        "{order}: declined, reason noted. Thank you, {name}.": "{order}：已拒绝，原因已记录。谢谢，{name}。",
        "{order}: completed. Thank you, {name}. You are free for new work now.": "{order}：已完成。谢谢，{name}。您现在可以接新单了。",
        "{order}: completed. Thank you, {name}. You have room again: {days} days of work left.": "{order}：已完成。谢谢，{name}。您还有 {days} 天的工作。",
        "{order}: thank you, the team has been told: {reason}.": "{order}：谢谢，已通知团队：{reason}。",
        "{order}: thank you, the team has been told it is {days} days late.": "{order}：谢谢，已通知团队将延迟 {days} 天。",
        "Job cards will now come in English.": "今后工单将以中文发送。",
    },
}


def say(lang: str, text: str, **fields) -> str:
    """The English wording, or its translation, with the fields filled in. Reasons in the fields are translated too."""
    table = WORDS.get(lang, {})
    return table.get(text, text).format(**{k: table.get(v, v) if isinstance(v, str) else v for k, v in fields.items()})


def goods(lang: str, job, english: str) -> str:
    name = PRODUCTS.get(lang, {}).get(job["product"])
    return f"{job['pieces']:,} {name}" if name else english
