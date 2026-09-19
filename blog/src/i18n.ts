export type Locale = 'zh' | 'en';

export const defaultLocale: Locale = 'zh';

export const ui = {
  zh: {
    siteName: '理财入门',
    siteKicker: '晚间课',
    tagline: '仅供学习，不构成投资建议。',
    home: '首页',
    articles: '文章',
    read: '阅读全文',
    source: '来源 Notion',
    published: '发布于',
    backHome: '返回目录',
    langNote: '界面可切换英文；正文目前以中文发布。',
    empty: '还没有文章。',
    footerCopy: '教育用途。不推荐买入或卖出任何股票、基金或数字币。',
    banner: '本页仅供学习，不构成任何投资建议；不推荐买入/卖出任何具体股票、基金或数字币。投资有风险，决策需自负。',
    latest: '课程目录',
    intro:
      '把日常理财简报做成可反复查阅的课次：市场怎么读、词怎么解、新闻怎么拆，作业怎么写。',
    originalZh: '中文正文',
    skip: '跳到正文',
    notFound: '没有找到这一页。',
    notFoundHint: '回目录看看最近的课次。',
  },
  en: {
    siteName: 'Finance Primer',
    siteKicker: 'Evening Lesson',
    tagline: 'For learning only — not investment advice.',
    home: 'Home',
    articles: 'Articles',
    read: 'Read article',
    source: 'Notion source',
    published: 'Published',
    backHome: 'Back to index',
    langNote: 'The interface is in English; this lesson body is in Chinese.',
    empty: 'No posts yet.',
    footerCopy: 'Educational use only. Does not recommend buying or selling any ticker, fund, or coin.',
    banner:
      'For learning only — not investment advice. This site does not recommend buying or selling any stock, fund, or coin. Investing involves risk; decisions are yours.',
    latest: 'Lesson index',
    intro:
      'Evening briefs turned into lessons you can revisit: how to read markets, one term at a time, headlines without the hype, plus homework.',
    originalZh: 'Chinese original',
    skip: 'Skip to content',
    notFound: 'This page is missing.',
    notFoundHint: 'Head back to the lesson index.',
  },
} as const;

export function localizePath(path: string, locale: Locale): string {
  const clean = path.replace(/^\/en(?=\/|$)/, '') || '/';
  if (locale === 'en') {
    return clean === '/' ? '/en' : `/en${clean}`;
  }
  return clean;
}

export function formatDate(date: Date, locale: Locale): string {
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth() + 1;
  const day = date.getUTCDate();
  if (locale === 'zh') {
    return `${year}年${month}月${day}日`;
  }
  const months = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];
  return `${months[month - 1]} ${day}, ${year}`;
}

export function displayTitle(
  post: { title: string; titleEn?: string },
  locale: Locale,
): string {
  return locale === 'en' && post.titleEn ? post.titleEn : post.title;
}

export function displayDescription(
  post: { description: string; descriptionEn?: string },
  locale: Locale,
): string {
  return locale === 'en' && post.descriptionEn ? post.descriptionEn : post.description;
}
