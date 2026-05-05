import re
from typing import List, Tuple, Optional


class ChannelClassifier:

    PROVINCES = [
        '通用', '山东', '北京', '上海', '广东', '浙江', '江苏',
        '湖南', '湖北', '四川', '天津', '重庆', '辽宁', '黑龙江',
        '吉林', '安徽', '河北', '河南', '江西', '福建', '陕西',
        '山西', '云南', '贵州', '甘肃', '内蒙古', '宁夏', '青海',
        '新疆', '西藏', '海南', '广西',
    ]

    def __init__(self, local_province: str = '通用'):
        self.local_province = local_province
        self.rules = self._build_rules()

    def _build_rules(self) -> List[Tuple[re.Pattern, str, str, Optional[str]]]:
        rules = []

        cctv_channels = [
            (r'^CCTV5\+', '央视频道', 'CCTV05+'),
            (r'^CCTV4K', '央视频道', 'CCTV4K'),
            (r'^CCTV8K', '央视频道', 'CCTV8K'),
            (r'^CCTV16五环', '央视频道', 'CCTV16'),
            (r'^CCTV4欧洲', '央视频道', 'CCTV4E'),
            (r'^CCTV4美洲', '央视频道', 'CCTV4A'),
            (r'^CCTV(\d+)', '央视频道', 'CCTV'),
            (r'^CCTV-', '央视频道', 'CCTV'),
            (r'^CGTN', '央视频道', 'CGTN'),
            (r'^CNC', '央视频道', 'CNC'),
            (r'^中国教育', '央视频道', 'CETV'),
            (r'^CETV', '央视频道', 'CETV'),
            (r'^风云音乐', '央视频道', 'CCTV风云音乐'),
            (r'^风云足球', '央视频道', 'CCTV风云足球'),
            (r'^风云剧场', '央视频道', 'CCTV风云剧场'),
            (r'^第一剧场', '央视频道', 'CCTV第一剧场'),
            (r'^兵器科技', '央视频道', 'CCTV兵器科技'),
            (r'^怀旧剧场', '央视频道', 'CCTV怀旧剧场'),
            (r'^女性时尚', '央视频道', 'CCTV女性时尚'),
            (r'^世界地理', '央视频道', 'CCTV世界地理'),
            (r'^卫生健康', '央视频道', 'CCTV卫生健康'),
            (r'^央视台球', '央视频道', 'CCTV央视台球'),
            (r'^央视文化精品', '央视频道', 'CCTV央视文化精品'),
            (r'^高尔夫网球', '央视频道', 'CCTV高尔夫网球'),
            (r'^电视指南', '央视频道', 'CCTV电视指南'),
            (r'^国防军事', '央视频道', 'CCTV7'),
            (r'^奥林匹克', '央视频道', 'CCTV16'),
            (r'^农业农村', '央视频道', 'CCTV17'),
            (r'^体育赛事', '央视频道', 'CCTV5+'),
            (r'^发现之旅', '央视频道', 'CCTV发现之旅'),
            (r'^老故事', '央视频道', 'CCTV老故事'),
            (r'^中学生', '央视频道', 'CCTV中学生'),
            (r'^CT4', '央视频道', 'CCTV4A'),
        ]
        for pattern, cat, key in cctv_channels:
            rules.append((re.compile(pattern, re.IGNORECASE), cat, key, None))

        hk_mo_tw = [
            (r'^TVB', '港澳台频道', 'TVB'),
            (r'^ViuTV', '港澳台频道', 'ViuTV'),
            (r'^凤凰', '港澳台频道', '凤凰'),
            (r'^澳门', '港澳台频道', '澳门'),
            (r'^澳视', '港澳台频道', '澳门'),
            (r'^澳亚', '港澳台频道', '澳门'),
            (r'^香港', '港澳台频道', '香港'),
            (r'^民视', '港澳台频道', '民视'),
            (r'^三立', '港澳台频道', '三立'),
            (r'^中视', '港澳台频道', '中视'),
            (r'^台视', '港澳台频道', '台视'),
            (r'^华视', '港澳台频道', '华视'),
            (r'^纬来', '港澳台频道', '纬来'),
            (r'^东森', '港澳台频道', '东森'),
            (r'^龙华', '港澳台频道', '龙华'),
            (r'^八大', '港澳台频道', '八大'),
            (r'^年代', '港澳台频道', '年代'),
            (r'^壹电视', '港澳台频道', '壹电视'),
            (r'^壹新闻', '港澳台频道', '壹新闻'),
            (r'^壹综合', '港澳台频道', '壹综合'),
            (r'^中天', '港澳台频道', '中天'),
            (r'^原住民', '港澳台频道', '原住民'),
            (r'^人间卫视', '港澳台频道', '人间卫视'),
            (r'^霹雳', '港澳台频道', '霹雳'),
            (r'^星空', '港澳台频道', '星空'),
            (r'^长城', '港澳台频道', '长城'),
            (r'^新时代', '港澳台频道', '新时代'),
            (r'^亚太', '港澳台频道', '亚太'),
            (r'^阳光', '港澳台频道', '阳光'),
            (r'^有线\d', '港澳台频道', '有线'),
            (r'^赛马', '港澳台频道', '赛马'),
            (r'^城市电视', '港澳台频道', '城市电视'),
            (r'^美亚电影', '港澳台频道', '美亚电影'),
            (r'^龙祥电影', '港澳台频道', '龙祥电影'),
            (r'^黄金华剧', '港澳台频道', '黄金华剧'),
            (r'^DAZN', '港澳台频道', 'DAZN'),
            (r'^beIN', '港澳台频道', 'beIN'),
        ]
        for pattern, cat, key in hk_mo_tw:
            rules.append((re.compile(pattern, re.IGNORECASE), cat, key, None))

        satellite_channels = [
            '北京卫视', '东方卫视', '湖南卫视', '浙江卫视', '江苏卫视',
            '广东卫视', '深圳卫视', '山东卫视', '四川卫视', '天津卫视',
            '重庆卫视', '河北卫视', '河南卫视', '湖北卫视', '安徽卫视',
            '江西卫视', '辽宁卫视', '黑龙江卫视', '吉林卫视', '云南卫视',
            '贵州卫视', '陕西卫视', '山西卫视', '广西卫视', '新疆卫视',
            '内蒙古卫视', '宁夏卫视', '西藏卫视', '青海卫视', '海南卫视',
            '甘肃卫视', '东南卫视', '农林卫视', '厦门卫视', '延边卫视',
            '三沙卫视', '大湾区卫视', '兵团卫视',
        ]
        for name in satellite_channels:
            province = name.replace('卫视', '')
            rules.append((re.compile(f'^{name}'), '卫视频道', name, province if province != '兵团' else '新疆'))
        rules.append((re.compile(r'^(.{2,3})卫视'), '卫视频道', None, None))

        province_map = {
            '北京': ['北京(?!卫视)', '北京'],
            '上海': ['上海(?!卫视)', '游戏风云', '法治天地', '都市频道', '生活时尚',
                     '金色频道', '欢笑剧场', '纪实人文', '新闻综合', '第一财经'],
            '广东': ['广东(?!卫视)', '深圳(?!卫视)'],
            '浙江': ['浙江(?!卫视)', '杭州', '宁波', '温州', '绍兴', '嘉兴',
                     '金华', '台州', '湖州', '丽水', '衢州', '舟山', '之江'],
            '江苏': ['江苏(?!卫视)'],
            '湖南': ['湖南(?!卫视)'],
            '湖北': ['湖北(?!卫视)'],
            '四川': ['四川(?!卫视)'],
            '天津': ['天津(?!卫视)'],
            '重庆': ['重庆(?!卫视)'],
            '辽宁': ['辽宁(?!卫视)'],
            '黑龙江': ['黑龙江(?!卫视)'],
            '吉林': ['吉林(?!卫视)'],
            '安徽': ['安徽(?!卫视)'],
            '河北': ['河北(?!卫视)'],
            '河南': ['河南(?!卫视)'],
            '江西': ['江西(?!卫视)'],
            '福建': ['福建'],
            '陕西': ['陕西(?!卫视)'],
            '山西': ['山西(?!卫视)'],
            '云南': ['云南(?!卫视)'],
            '贵州': ['贵州(?!卫视)'],
            '甘肃': ['甘肃(?!卫视)'],
            '内蒙古': ['内蒙古(?!卫视)'],
            '宁夏': ['宁夏(?!卫视)'],
            '青海': ['青海(?!卫视)'],
            '新疆': ['新疆(?!卫视)'],
            '西藏': ['西藏(?!卫视)'],
            '海南': ['海南(?!卫视)'],
            '广西': ['广西(?!卫视)'],
            '山东': ['山东(?!卫视)', '济南', '青岛', '烟台', '潍坊', '淄博',
                     '济宁', '临沂', '威海', '德州', '聊城', '菏泽', '泰安',
                     '滨州', '枣庄', '日照', '东营', '莱芜', 'QTV'],
        }
        for province, patterns in province_map.items():
            for p in patterns:
                rules.append((re.compile(p), f'{province}频道', province, province))

        paid_channels = [
            (r'^CHC', '付费频道', 'CHC'),
            (r'^家庭影院', '付费频道', 'CHC家庭影院'),
            (r'^动作电影', '付费频道', 'CHC动作电影'),
            (r'^NewTV', '付费频道', 'NewTV'),
            (r'^iHOT', '付费频道', 'iHOT'),
            (r'^华数', '付费频道', '华数'),
            (r'^咪咕', '付费频道', '咪咕'),
            (r'^咪视界', '付费频道', '咪视界'),
            (r'^爱大剧', '付费频道', '爱大剧'),
            (r'^爱电影', '付费频道', '爱电影'),
            (r'^爱生活', '付费频道', '爱生活'),
            (r'^爱体育', '付费频道', '爱体育'),
            (r'^爱综艺', '付费频道', '爱综艺'),
            (r'^爱上4K', '付费频道', '爱上4K'),
            (r'^熊猫频道', '付费频道', '熊猫频道'),
            (r'^高清大片', '付费频道', '高清大片'),
            (r'^经典电影', '付费频道', '经典电影'),
            (r'^军事大片', '付费频道', '军事大片'),
            (r'^热剧联播', '付费频道', '热剧联播'),
            (r'^赛事经典', '付费频道', '赛事经典'),
            (r'^体坛名汇', '付费频道', '体坛名汇'),
            (r'^新片映厅', '付费频道', '新片映厅'),
            (r'^四海钓鱼', '付费频道', '四海钓鱼'),
            (r'^摄影频道', '付费频道', '摄影频道'),
        ]
        for pattern, cat, key in paid_channels:
            rules.append((re.compile(pattern, re.IGNORECASE), cat, key, None))

        return rules

    def classify(self, name: str) -> dict:
        if not name:
            return {'category': '其他频道', 'sort_key': '', 'province': None}

        for pattern, category, sort_key, province in self.rules:
            m = pattern.match(name)
            if m:
                key = sort_key
                if key is None and m.lastindex and m.lastindex >= 1:
                    key = m.group(1) + '卫视'
                elif key == 'CCTV' and m.lastindex and m.lastindex >= 1:
                    try:
                        num = int(m.group(1))
                        key = f'CCTV{num:02d}'
                    except ValueError:
                        key = 'CCTV'
                return {'category': category, 'sort_key': key or name, 'province': province}

        return {'category': '其他频道', 'sort_key': name, 'province': None}

    def classify_all(self, channels: list, overwrite: bool = False) -> list:
        results = []
        for ch in channels:
            name = ch.get('name', '')
            result = self.classify(name)
            category = result['category']

            if result['province']:
                if self.local_province == '通用':
                    category = result['province'] + '频道'
                elif result['province'] == self.local_province:
                    category = self.local_province + '频道'
                else:
                    category = '其他频道'

            current_group = ch.get('group', '')
            if not overwrite and current_group and current_group.strip():
                results.append({
                    'index': ch.get('_index', 0),
                    'name': name,
                    'old_group': current_group,
                    'new_group': current_group,
                    'sort_key': result['sort_key'],
                    'changed': False,
                })
            else:
                results.append({
                    'index': ch.get('_index', 0),
                    'name': name,
                    'old_group': current_group,
                    'new_group': category,
                    'sort_key': result['sort_key'],
                    'changed': category != current_group,
                })
        return results

    def get_category_order(self) -> list:
        base = ['央视频道', '卫视频道']
        if self.local_province != '通用':
            base.append(self.local_province + '频道')
        base.extend(['港澳台频道', '付费频道', '其他频道'])
        return base

    def sort_classified(self, channels: list) -> list:
        category_order = self.get_category_order()

        def sort_key(ch):
            cat = ch.get('new_group', ch.get('group', ''))
            cat_idx = category_order.index(cat) if cat in category_order else 99
            return (cat_idx, ch.get('sort_key', ch.get('name', '')))

        return sorted(channels, key=sort_key)
