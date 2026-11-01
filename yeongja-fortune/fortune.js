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

  var TEXT = {
    great: {
      head: ['복이 문 두드리는 날', '술술 풀리는 날', '웃을 일 생기는 날'],
      say: ['들어오는 복, 문 열어 두세요.', '오늘은 영자가 장담해요.', '미뤄둔 일, 오늘 하세요.']
    },
    same: {
      head: ['내 기운 센 날', '밀어붙여도 되는 날'],
      say: ['오늘은 내가 주인공이에요.', '하고 싶던 말, 해도 돼요.']
    },
    normal: {
      head: ['잔잔해서 좋은 날', '평소대로가 복인 날', '무난하게 흘러가는 날'],
      say: ['별일 없는 게 제일 큰 복이에요.', '오늘은 마음 편히 쉬세요.']
    },
    wonjin: {
      head: ['말 한마디 아끼는 날', '서운함 넘기는 날'],
      say: ['서운한 말은 내일 하세요.', '한 번만 웃고 넘기세요.']
    },
    chung: {
      head: ['한 박자 쉬어 가는 날', '서두르면 손해 보는 날'],
      say: ['천천히 가도 늦지 않아요.', '오늘은 큰일 미루세요.']
    }
  };

  // 오늘 들어오는 복: [이름, 짧은 설명]
  var BOK = [
    ['재물복', '뜻밖의 돈이 들어와요'],
    ['자식복', '자식에게서 기쁜 소식'],
    ['손주복', '손주 재롱에 웃어요'],
    ['건강복', '몸이 가볍고 개운해요'],
    ['인복', '귀한 사람이 찾아와요'],
    ['먹을복', '맛있는 걸 얻어먹어요'],
    ['웃음복', '크게 웃을 일 생겨요'],
    ['부부복', '배우자와 정이 깊어져요'],
    ['문서복', '서류 일이 술술 풀려요'],
    ['나들이복', '바깥바람이 약이 돼요']
  ];
  var CAREFUL = ['말 한마디', '충동구매', '보증·돈 빌려주기', '찬 음식', '계단·빙판',
    '급한 운전', '남의 일 참견', '모르는 전화', '뜨거운 물', '늦은 밤 과식',
    '약속 시간', '허리 무리', '지갑 분실', '큰 결정'];
  var CAREFUL_CHUNG = ['급한 운전', '계단·빙판', '큰 결정', '허리 무리', '모르는 전화'];

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

    var bok = pick(BOK);
    var careful = pick(rel === 'chung' ? CAREFUL_CHUNG : CAREFUL);

    return {
      animal: ANIMALS[myBranch],
      emoji: ANIMAL_EMOJI[myBranch],
      yy: String(by).slice(2),
      dayName: STEMS[day.stem] + BRANCHES[day.branch] + '일',
      date: tm + '월 ' + td + '일',
      level: rel,
      head: pick(TEXT[rel].head),
      say: pick(TEXT[rel].say),
      bok: bok[0],
      bokDesc: bok[1],
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
