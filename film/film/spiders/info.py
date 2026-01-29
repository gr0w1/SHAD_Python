import scrapy
import re

class InfoSpider(scrapy.Spider):
    name = "info"
    allowed_domains = ["ru.wikipedia.org", "imdb.com", "www.imdb.com"]
    start_urls = ["https://ru.wikipedia.org/wiki/Категория:Фильмы_по_алфавиту"]

    # собираем рейтинг из IMDb в фильм, который передали по метадате
    def parse_imdb(self, response):
        result = response.meta['result']
        rating = response.css('div[data-testid="hero-rating-bar__aggregate-rating__score"] span::text').get()
        # если рейтинг не найден оставляем поле пустым
        result['imdb'] = rating if rating else ''
        yield result

    # собираем данные по 1 фильму
    def parse_film(self, response):
        canon_keys = {'Жанры':'genre',
                      'Жанр':'genre',
                      'Режиссер':'director',
                      'Режиссёр': 'director',
                      'Режиссеры': 'director',
                      'Режиссёры': 'director',
                      'Страна':'country',
                      'Страны':'country',
                      'Год':'year',
                      'Годы':'year'
                      }
        result = dict()
        # название через главный заголовок
        result['title'] = response.css('#firstHeading span::text').get()
        # итерируемся по таблице сбоку и смотрим, подходит ли нам ключ
        for row in response.xpath('//table[contains(@class,"infobox")]//tr[th[@scope="row"]]'):
            # сначала пытаемся достать ключ и значение из ссылки
            key = ' '.join(t.strip() for t in row.css("th[scope='row'] a *::text, th[scope='row'] a::text").getall() if t.strip())
            value = ' '.join(t.strip() for t in row.css("td a *::text, td a::text").getall() if t.strip())
            # если нет ссылки в поле, то будем искать любой текст, отсеивая мусор и убирая сноски
            if key=='':
                key = ' '.join(
                    t.strip() for t in row.css(":not(sup):not(style) th[scope='row'] *::text, :not(sup):not(style) th[scope='row']::text").getall() if
                    t.strip())
            if value=='':
                value = ' '.join(t.strip() for t in row.css("td *::text, td::text").getall() if t.strip())
            # если ключ не из тех данных которые собираем, то пропускаем
            if key in canon_keys:
                result[canon_keys[key]] = re.sub(r"\[\s*(\d+|вд)\s*\]", "", value).strip()

        # берем url для перехода в IMDb
        film_url = response.xpath('//a[contains(@href, "imdb.com/title/tt")]/@href').get()

        # переходим по ссылке если возможно и передаем те поля, что уже собрали и парсим рейтинг
        if film_url:
            yield scrapy.Request(
                url=film_url,
                callback=self.parse_imdb,
                meta={'result': result},
                dont_filter=True
            )
        else:
            result['imdb'] = ''
            yield result

    # парсинг всех фильмов
    def parse(self, response):
        # для каждой строки с фильмом из списка переходим на страницу фильма и передаем управление другой функции парсинга
        for href in response.css('div.mw-category.mw-category-columns li a::attr(href)').getall():
            yield response.follow(href, callback=self.parse_film)

        # пока можем, ищем и переходим на следующую страницу с фильмами
        next_href = response.xpath('//div[@id="mw-pages"]//a[contains(normalize-space(.), "Следующая страница")]/@href').get()
        if next_href:
            yield response.follow(next_href, callback=self.parse)
