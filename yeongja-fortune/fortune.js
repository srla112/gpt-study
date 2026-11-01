// 영자의 오늘 운세 — 계산 로직
// 브라우저와 Node(테스트) 양쪽에서 쓸 수 있게 만든다.
(function (root) {
  'use strict';

  var STEMS = ['갑', '을', '병', '정', '무', '기', '경', '신', '임', '계'];
  var BRANCHES = ['자', '축', '인', '묘', '진', '사', '오', '미', '신', '유', '술', '해'];
  var ANIMALS = ['쥐', '소', '범', '토끼', '용', '뱀', '말', '양', '원숭이', '닭', '개', '돼지'];
  var ANIMAL_EMOJI = ['🐭', '🐮', '🐯', '🐰', '🐲', '🐍', '🐴', '🐑', '🐵', '🐔', '🐶', '🐷'];

  // 오행: 0 목, 1 화, 2 토, 3 금, 4 수
  var ELEMENTS = [
    { name: '목', colors: [{ n: '초록', c: '#3f7d4a' }, { n: '연두', c: '#8dbb5a' }], numbers: [3, 8], dir: '동쪽' },
    { name: '화', colors: [{ n: '빨강', c: '#c0392b' }, { n: '분홍', c: '#e58fa0' }], numbers: [2, 7], dir: '남쪽' },
    { name: '토', colors: [{ n: '노랑', c: '#e0b02a' }, { n: '황토', c: '#b07a3b' }], numbers: [5, 10], dir: '남서쪽' },
    { name: '금', colors: [{ n: '흰색', c: '#f7f3e8' }, { n: '금색', c: '#c9a24a' }], numbers: [4, 9], dir: '서쪽' },
    { name: '수', colors: [{ n: '남색', c: '#1f3a68' }, { n: '검정', c: '#222222' }], numbers: [1, 6], dir: '북쪽' }
  ];

  // 율리우스 적일(JDN). 2000-01-01 = 2451545
  function jdn(y, m, d) {
    var a = Math.floor((14 - m) / 12);
    var yy = y + 4800 - a;
    var mm = m + 12 * a - 3;
    return d + Math.floor((153 * mm + 2) / 5) + 365 * yy + Math.floor(yy / 4) -
      Math.floor(yy / 100) + Math.floor(yy / 400) - 32045;
  }

  // 그날의 일진(간지). 2000-01-01 = 무오일
  function dayPillar(y, m, d) {
    var j = jdn(y, m, d);
    return { stem: (j + 9) % 10, branch: (j + 1) % 12 };
  }

  // 띠는 태어난 해 기준(설·입춘 경계는 단순화)
  function yearBranch(y) { return ((y - 4) % 12 + 12) % 12; }
  function yearStem(y) { return ((y - 4) % 10 + 10) % 10; }
  function stemElement(s) { return Math.floor(s / 2); }

  var SAMHAP = [[8, 0, 4], [11, 3, 7], [2, 6, 10], [5, 9, 1]];
  var YUKHAP = { 0: 1, 1: 0, 2: 11, 11: 2, 3: 10, 10: 3, 4: 9, 9: 4, 5: 8, 8: 5, 6: 7, 7: 6 };
  var WONJIN = { 0: 7, 7: 0, 1: 6, 6: 1, 2: 9, 9: 2, 3: 8, 8: 3, 4: 11, 11: 4, 5: 10, 10: 5 };

  // 내 띠와 오늘 일지의 관계
  function relation(me, day) {
    if (me === day) return 'same';
    if (YUKHAP[me] === day) return 'great';
    for (var i = 0; i < SAMHAP.length; i++) {
      if (SAMHAP[i].indexOf(me) >= 0 && SAMHAP[i].indexOf(day) >= 0) return 'great';
    }
    if ((me + 6) % 12 === day) return 'chung';
    if (WONJIN[me] === day) return 'wonjin';
    return 'normal';
  }

  // 같은 사람·같은 날이면 항상 같은 결과가 나오게 하는 해시
  function hash(str) {
    var h = 2166136261;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }
  function picker(seed) {
    var s = seed || 1;
    return function (arr) {
      s ^= s << 13; s >>>= 0;
      s ^= s >>> 17;
      s ^= s << 5; s >>>= 0;
      return arr[s % arr.length];
    };
  }

  // 그날의 기운별 사자성어 [한글, 한자, 풀이], 좋은 일, 영자 한마디
  var TEXT = {
    great: {
      saja: [['운수대통', '運數大通', '운이 크게 트이는 날'],
             ['만사형통', '萬事亨通', '모든 일이 뜻대로 되는 날'],
             ['금상첨화', '錦上添花', '좋은 일에 좋은 일이 겹치는 날'],
             ['소원성취', '所願成就', '바라던 일이 이루어지는 날']],
      good: ['막혔던 일이 술술 풀립니다.', '반가운 소식이 들려옵니다.', '뜻밖의 돈이 들어옵니다.',
             '귀한 사람을 만납니다.', '자식 일로 웃을 일이 생깁니다.'],
      say: ['오늘은 웃을 일만 있을 거예요.', '좋은 기운, 꼭 붙잡으세요.']
    },
    same: {
      saja: [['승승장구', '乘勝長驅', '기세 좋게 뻗어 나가는 날'],
             ['일취월장', '日就月將', '하는 일마다 나아지는 날']],
      good: ['마음먹은 일을 시작하기 좋습니다.', '오래 바라던 일에 길이 보입니다.', '하는 말에 힘이 실립니다.'],
      say: ['오늘은 마음먹은 대로 하세요.']
    },
    normal: {
      saja: [['무사태평', '無事泰平', '걱정 없이 편안한 날'],
             ['안분지족', '安分知足', '가진 것에 감사하면 복이 되는 날'],
             ['유비무환', '有備無患', '미리 챙기면 걱정 없는 날']],
      good: ['집안이 두루 편안합니다.', '오랜 친구 소식이 반갑습니다.', '작은 기쁨이 쌓이는 하루입니다.',
             '몸과 마음이 편안합니다.'],
      say: ['별일 없는 게 제일 큰 복이에요.', '오늘도 무탈하게 보내세요.']
    },
    wonjin: {
      saja: [['역지사지', '易地思之', '상대 입장에서 생각하면 풀리는 날'],
             ['인지위덕', '忍之爲德', '참는 것이 덕이 되는 날'],
             ['구시화문', '口是禍門', '입을 무겁게 해야 하는 날']],
      good: ['한 번 참으면 나중에 웃습니다.', '먼저 웃으면 마음이 풀립니다.', '가족과 함께하면 마음이 놓입니다.'],
      say: ['서운한 말은 한 번 참으세요.']
    },
    chung: {
      saja: [['심사숙고', '深思熟考', '깊이 생각하고 움직일 날'],
             ['자중자애', '自重自愛', '몸과 마음을 아껴야 하는 날'],
             ['유비무환', '有備無患', '미리 챙기면 걱정 없는 날']],
      good: ['한 걸음 물러서면 길이 보입니다.', '집에서 쉬면 복이 됩니다.', '가족과 함께하면 마음이 놓입니다.'],
      say: ['천천히 가도 늦지 않아요.']
    }
  };

  var CAREFUL = ['돈 빌려주면 못 받습니다.', '보증은 서지 마세요.', '말 한마디가 화를 부릅니다.',
    '남의 일에 끼어들지 마세요.', '모르는 전화는 받지 마세요.', '계단에서 발밑을 살피세요.',
    '찬 음식은 탈이 납니다.', '충동구매는 후회합니다.', '밤늦게 많이 드시지 마세요.', '지갑을 잘 챙기세요.'];
  var CAREFUL_CHUNG = ['운전은 천천히 하세요.', '큰돈 드는 결정은 미루세요.', '무거운 것은 들지 마세요.',
    '계단에서 발밑을 살피세요.', '모르는 전화는 받지 마세요.'];

  // input: { year: 1960 } — 태어난 해만 받는다. today: Date
  function getFortune(input, today) {
    var by = Number(input.year);
    var t = today || new Date();
    var ty = t.getFullYear(), tm = t.getMonth() + 1, td = t.getDate();

    var myBranch = yearBranch(by);
    var day = dayPillar(ty, tm, td);
    var rel = relation(myBranch, day.branch);

    var key = [by, ty, tm, td].join('|');
    var pick = picker(hash(key));

    // 행운 오행: 나를 돕는 기운(인성), 내 기운, 오늘 일간의 기운 중 하나
    var myEl = stemElement(yearStem(by));
    var supportEl = (myEl + 4) % 5;
    var dayEl = stemElement(day.stem);
    var candidates = [supportEl, supportEl, myEl];
    if ((dayEl + 2) % 5 !== myEl) candidates.push(dayEl); // 오늘 기운이 나를 누르지 않을 때만
    var el = ELEMENTS[pick(candidates)];

    var careful = pick(rel === 'chung' ? CAREFUL_CHUNG : CAREFUL);

    return {
      animal: ANIMALS[myBranch],
      emoji: ANIMAL_EMOJI[myBranch],
      yy: String(by).slice(2),
      dayName: STEMS[day.stem] + BRANCHES[day.branch] + '일',
      date: tm + '월 ' + td + '일',
      level: rel,
      saja: pick(TEXT[rel].saja),
      good: pick(TEXT[rel].good),
      say: pick(TEXT[rel].say),
      careful: careful,
      color: pick(el.colors),
      number: pick(el.numbers),
      direction: el.dir
    };
  }

  var api = { ANIMALS: ANIMALS, ANIMAL_EMOJI: ANIMAL_EMOJI, getFortune: getFortune, dayPillar: dayPillar, yearBranch: yearBranch, relation: relation };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.YeongjaFortune = api;
})(this);
