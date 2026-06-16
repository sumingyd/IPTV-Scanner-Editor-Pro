import re
from typing import Optional, List, Tuple, Callable, Union
from re import Pattern

LogoRule = Tuple[Pattern, Union[str, Callable[[re.Match], Optional[str]]]]


class LogoMatcher:

    LOGO_BASE_URL = 'https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/img/'

    def __init__(self, base_url: Optional[str] = None):
        self.base_url: str = base_url if base_url is not None else self.LOGO_BASE_URL
        self.rules: List[LogoRule] = self._build_rules()

    def _build_rules(self) -> List[LogoRule]:
        rules: List[LogoRule] = []

        rules.extend([
            (re.compile(r'^CCTV5\+', re.IGNORECASE), 'CCTV5+.png'),
            (re.compile(r'^CCTV4K', re.IGNORECASE), 'CCTV4K.png'),
            (re.compile(r'^CCTV16五环', re.IGNORECASE), 'CCTV16五环.png'),
            (re.compile(r'^CCTV16', re.IGNORECASE), 'CCTV16.png'),
            (re.compile(r'^CCTV4欧洲', re.IGNORECASE), 'CCTV4欧洲.png'),
            (re.compile(r'^CCTV4美洲', re.IGNORECASE), 'CCTV4美洲.png'),
            (re.compile(r'^CCTV中视购物', re.IGNORECASE), 'CCTV中视购物.png'),
            (re.compile(r'^CCTV(\d+)', re.IGNORECASE), lambda m: f'CCTV{m.group(1)}.png'),
        ])

        rules.extend([
            (re.compile(r'^CGTN俄语'), 'CGTN俄语.png'),
            (re.compile(r'^CGTN法语'), 'CGTN法语.png'),
            (re.compile(r'^CGTN阿语'), 'CGTN阿语.png'),
            (re.compile(r'^CGTN西语'), 'CGTN西语.png'),
            (re.compile(r'^CGTN纪录'), 'CGTN纪录.png'),
            (re.compile(r'^CGTN'), 'CGTN.png'),
        ])

        rules.extend([
            (re.compile(r'^CETV1', re.IGNORECASE), 'CETV1.png'),
            (re.compile(r'^CETV2', re.IGNORECASE), 'CETV2.png'),
            (re.compile(r'^CETV3', re.IGNORECASE), 'CETV3.png'),
            (re.compile(r'^CETV4', re.IGNORECASE), 'CETV4.png'),
            (re.compile(r'^中国教育1'), 'CETV1.png'),
            (re.compile(r'^中国教育2'), 'CETV2.png'),
            (re.compile(r'^中国教育4'), 'CETV4.png'),
        ])

        rules.extend([
            (re.compile(r'^QTV(\d+)', re.IGNORECASE), lambda m: f'QTV{m.group(1)}.png'),
        ])

        satellite_4k = [
            '北京卫视', '东方卫视', '湖南卫视', '浙江卫视', '江苏卫视',
            '广东卫视', '深圳卫视', '山东卫视', '四川卫视',
        ]
        for name in satellite_4k:
            rules.append((re.compile(f'^{name}4K'), f'{name}4K.png'))

        satellite_logos = [
            '北京卫视', '东方卫视', '湖南卫视', '浙江卫视', '江苏卫视',
            '广东卫视', '深圳卫视', '山东卫视', '四川卫视', '天津卫视',
            '重庆卫视', '河北卫视', '河南卫视', '湖北卫视', '安徽卫视',
            '江西卫视', '辽宁卫视', '黑龙江卫视', '吉林卫视', '云南卫视',
            '贵州卫视', '陕西卫视', '山西卫视', '广西卫视', '新疆卫视',
            '内蒙古卫视', '宁夏卫视', '西藏卫视', '青海卫视', '海南卫视',
            '甘肃卫视', '东南卫视', '农林卫视', '厦门卫视', '延边卫视',
            '三沙卫视', '兵团卫视',
        ]
        for name in satellite_logos:
            rules.append((re.compile(f'^{name}'), f'{name}.png'))

        rules.append((re.compile(r'^(.{2,3})卫视'), lambda m: f'{m.group(1)}卫视.png'))

        rules.extend([
            (re.compile(r'^凤凰中文'), '凤凰中文.png'),
            (re.compile(r'^凤凰资讯'), '凤凰资讯.png'),
            (re.compile(r'^凤凰香港'), '凤凰香港.png'),
            (re.compile(r'^凤凰卫视'), '凤凰卫视.png'),
        ])

        rules.extend([
            (re.compile(r'^澳门'), '澳门电视台.png'),
            (re.compile(r'^澳视'), '澳门电视台.png'),
            (re.compile(r'^澳亚'), '澳门电视台.png'),
        ])

        rules.extend([
            (re.compile(r'^风云音乐'), 'CCTV风云音乐.png'),
            (re.compile(r'^风云足球'), 'CCTV风云足球.png'),
            (re.compile(r'^风云剧场'), 'CCTV风云剧场.png'),
            (re.compile(r'^兵器科技'), 'CCTV兵器科技.png'),
            (re.compile(r'^怀旧剧场'), 'CCTV怀旧剧场.png'),
            (re.compile(r'^女性时尚'), 'CCTV女性时尚.png'),
            (re.compile(r'^世界地理'), 'CCTV世界地理.png'),
            (re.compile(r'^卫生健康'), 'CCTV卫生健康.png'),
            (re.compile(r'^央视台球'), 'CCTV央视台球.png'),
            (re.compile(r'^央视文化精品'), 'CCTV央视文化精品.png'),
            (re.compile(r'^高尔夫网球'), 'CCTV高尔夫网球.png'),
            (re.compile(r'^国防军事'), 'CCTV7.png'),
            (re.compile(r'^奥林匹克'), 'CCTV16.png'),
            (re.compile(r'^五环'), 'CCTV16五环.png'),
            (re.compile(r'^农业农村'), 'CCTV17.png'),
            (re.compile(r'^体育赛事'), 'CCTV5+.png'),
            (re.compile(r'^发现之旅'), '发现之旅.png'),
            (re.compile(r'^中学生'), '中学生.png'),
        ])

        rules.extend([
            (re.compile(r'^CHC动作电影'), 'CHC动作电影.png'),
            (re.compile(r'^CHC高清电影'), 'CHC高清电影.png'),
            (re.compile(r'^CHC家庭影院'), 'CHC家庭影院.png'),
            (re.compile(r'^CHC影迷电影'), 'CHC影迷电影.png'),
            (re.compile(r'^CHC'), 'CHC高清电影.png'),
        ])

        rules.extend([
            (re.compile(r'^家庭影院'), '家庭影院.png'),
            (re.compile(r'^咪咕影院'), '咪咕影院.png'),
            (re.compile(r'^咪视界'), '咪视界.png'),
            (re.compile(r'^爱上4K'), '爱上4K.png'),
            (re.compile(r'^纯享4K'), '纯享4K.png'),
            (re.compile(r'^多彩文体4K'), '多彩文体4K.png'),
            (re.compile(r'^至臻视界4K'), '至臻视界4K.png'),
            (re.compile(r'^欢笑剧场4K'), '欢笑剧场4K.png'),
        ])

        rules.extend([
            (re.compile(r'^中华特产'), '中华特产.png'),
            (re.compile(r'^中国交通'), '中国交通.png'),
            (re.compile(r'^中国天气'), '中国天气.png'),
            (re.compile(r'^书画'), '书画.png'),
            (re.compile(r'^优漫卡通'), '优漫卡通.png'),
            (re.compile(r'^优优宝贝'), '优优宝贝.png'),
            (re.compile(r'^先锋乒羽'), '先锋乒羽.png'),
            (re.compile(r'^军旅剧场'), '军旅剧场.png'),
            (re.compile(r'^动作影院'), '动作影院.png'),
            (re.compile(r'^动漫秀场'), '动漫秀场.png'),
            (re.compile(r'^卡酷少儿'), '卡酷少儿.png'),
            (re.compile(r'^古装剧场'), '古装剧场.png'),
            (re.compile(r'^嘉佳卡通'), '嘉佳卡通.png'),
            (re.compile(r'^哈哈炫动'), '哈哈炫动.png'),
            (re.compile(r'^四海钓鱼'), '四海钓鱼.png'),
            (re.compile(r'^城市剧场'), '城市剧场.png'),
            (re.compile(r'^家庭理财'), '家庭理财.png'),
            (re.compile(r'^快乐垂钓'), '快乐垂钓.png'),
            (re.compile(r'^新动漫'), '新动漫.png'),
            (re.compile(r'^新视觉'), '新视觉.png'),
            (re.compile(r'^武术世界'), '武术世界.png'),
            (re.compile(r'^求索纪录'), '求索纪录.png'),
            (re.compile(r'^求索动物'), '求索动物.png'),
            (re.compile(r'^求索科学'), '求索科学.png'),
            (re.compile(r'^求索生活'), '求索生活.png'),
            (re.compile(r'^汽摩'), '汽摩.png'),
            (re.compile(r'^法治天地'), '法治天地.png'),
            (re.compile(r'^游戏风云'), '游戏风云.png'),
            (re.compile(r'^环球旅游'), '环球旅游.png'),
            (re.compile(r'^生态环境'), '生态环境.png'),
            (re.compile(r'^生活时尚'), '生活时尚.png'),
            (re.compile(r'^精彩影视'), '精彩影视.png'),
            (re.compile(r'^红色影视'), '红色影视.png'),
            (re.compile(r'^红色影院'), '红色影视.png'),
            (re.compile(r'^经典剧场'), '经典剧场.png'),
            (re.compile(r'^谍战剧场'), '谍战剧场.png'),
            (re.compile(r'^都市剧场'), '都市剧场.png'),
            (re.compile(r'^重温经典影视'), '重温经典影视.png'),
            (re.compile(r'^重温经典'), '重温经典.png'),
            (re.compile(r'^金色学堂'), '金色学堂.png'),
            (re.compile(r'^金鹰卡通'), '金鹰卡通.png'),
            (re.compile(r'^金鹰纪实'), '金鹰纪实.png'),
            (re.compile(r'^魅力足球'), '魅力足球.png'),
            (re.compile(r'^天下足球'), '天下足球.png'),
            (re.compile(r'^睛彩广场舞'), '睛彩广场舞.png'),
            (re.compile(r'^睛彩竞技'), '睛彩竞技.png'),
            (re.compile(r'^睛彩篮球'), '睛彩篮球.png'),
            (re.compile(r'^睛彩青少'), '睛彩青少.png'),
            (re.compile(r'^纪实科教'), '纪实科教.png'),
            (re.compile(r'^乐游'), '乐游.png'),
            (re.compile(r'^东方财经'), '东方财经.png'),
            (re.compile(r'^广东体育'), '广东体育.png'),
            (re.compile(r'^梨园'), '梨园频道.png'),
            (re.compile(r'^九屏同看'), '九屏同看.png'),
            (re.compile(r'^华数'), '华数.png'),
            (re.compile(r'^央广购物'), '央广购物.png'),
            (re.compile(r'^哒啵电竞'), '哒啵电竞.png'),
            (re.compile(r'^翡翠剧集台'), '翡翠剧集台.png'),
            (re.compile(r'^财富天下'), '财富天下.png'),
            (re.compile(r'^茶频道'), '茶频道.png'),
            (re.compile(r'^车迷频道'), '车迷频道.png'),
            (re.compile(r'^文物宝库'), '文物宝库.png'),
            (re.compile(r'^黑莓电影'), '黑莓电影.png'),
            (re.compile(r'^黑莓动画'), '黑莓动画.png'),
            (re.compile(r'^DW德国之声'), 'DW德国之声.png'),
            (re.compile(r'^NHK世界台'), 'NHK世界台.png'),
        ])

        rules.extend([
            (re.compile(r'^山东教育卫视'), '山东教育卫视.png'),
            (re.compile(r'^山东交通广播'), '山东交通广播.png'),
            (re.compile(r'^山东经济广播'), '山东经济广播.png'),
            (re.compile(r'^山东综合广播'), '山东综合广播.png'),
            (re.compile(r'^山东农科'), '山东农科.png'),
            (re.compile(r'^山东齐鲁'), '山东齐鲁.png'),
            (re.compile(r'^山东少儿'), '山东少儿.png'),
            (re.compile(r'^山东生活'), '山东生活.png'),
            (re.compile(r'^山东体育'), '山东体育.png'),
            (re.compile(r'^山东文旅'), '山东文旅.png'),
            (re.compile(r'^山东新闻'), '山东新闻.png'),
            (re.compile(r'^山东综艺'), '山东综艺.png'),
            (re.compile(r'^居家购物'), '居家购物.png'),
            (re.compile(r'^山东居家购物'), '居家购物.png'),
            (re.compile(r'^海洋频道'), '海洋频道.png'),
            (re.compile(r'^山东海洋'), '海洋频道.png'),
            (re.compile(r'^山东(.+)'), lambda m: f'山东{m.group(1)}.png'),
        ])

        return rules

    def match(self, name: str) -> Optional[str]:
        if not name:
            return None

        for pattern, logo_file in self.rules:
            m = pattern.match(name)
            if m:
                if callable(logo_file):
                    result = logo_file(m)
                    if result:
                        return self.base_url + result
                    return None
                if logo_file:
                    return self.base_url + logo_file
                return None

        return None

    def match_all(self, channels: list, overwrite: bool = False) -> list:
        results = []
        for i, ch in enumerate(channels):
            name = ch.get('name', '')
            current_logo = ch.get('logo', '')
            if not overwrite and current_logo:
                continue
            logo = self.match(name)
            if logo:
                results.append({
                    'index': i,
                    'name': name,
                    'logo': logo,
                    'old_logo': current_logo,
                })
        return results
