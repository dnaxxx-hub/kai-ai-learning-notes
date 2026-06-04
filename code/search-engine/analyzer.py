"""analyzer.py — 分词器（中文分词 + 英文小写 + 去停用词）"""

import re

# 内置英文停用词
STOP_WORDS_EN = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
    'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
    'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
    'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
    'just', 'because', 'but', 'and', 'or', 'if', 'while', 'although',
    'the', 'this', 'that', 'these', 'those', 'i', 'me', 'my', 'myself',
    'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself',
    'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
    'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
    'what', 'which', 'who', 'whom', 'what', 'about', 'up', 'down',
}

# 中文常见停用词
STOP_WORDS_ZH = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
    '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着',
    '没有', '看', '好', '自己', '这', '他', '她', '它', '们', '那', '些',
    '为', '所', '以', '之', '与', '及', '但', '或', '被', '让', '从',
    '对', '把', '将', '能', '而', '等', '个', '中', '下', '里', '来',
    '出', '过', '时', '后', '前', '开', '还', '可', '已', '更', '最',
    '向', '比', '并', '吗', '呢', '啊', '哦', '嗯', '呀', '吧', '么',
    '哪', '谁', '怎', '么', '什', '怎么', '什么', '如何', '为何',
    '因', '为', '于', '其', '中', '如', '何', '此', '彼',
}


class Analyzer:
    """分词器"""

    def __init__(self, stop_words=None):
        self.stop_words = stop_words or STOP_WORDS_EN | STOP_WORDS_ZH

    def analyze(self, text):
        """分析文本，返回 token 列表"""
        if not text:
            return []

        text = str(text)
        tokens = self._tokenize(text.lower())

        # 去停用词 + 空词
        result = []
        for t in tokens:
            if t not in self.stop_words and t.strip():
                result.append(t)
        return result

    def _tokenize(self, text):
        """分词核心逻辑"""
        tokens = []
        i = 0
        current_word = ''
        while i < len(text):
            ch = text[i]
            if 'a' <= ch <= 'z':
                current_word += ch
            else:
                if current_word:
                    tokens.append(current_word)
                    current_word = ''
                # 中文/非英文字符：单个切分（如果非空白）
                if not ch.isspace() and ord(ch) > 127:
                    tokens.append(ch)
            i += 1
        if current_word:
            tokens.append(current_word)

        return [t for t in tokens if t.strip()]
