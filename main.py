import json
import os

import feedparser
from rx import config, Observable
from rx.subjects import Subject
from tornado.escape import json_decode
from tornado.httpclient import AsyncHTTPClient
from tornado.platform.asyncio import AsyncIOMainLoop
from tornado.web import Application, RequestHandler, StaticFileHandler, url
from tornado.websocket import WebSocketHandler

asyncio = config['asyncio']


class WSHandler(WebSocketHandler):
    urls = ['https://lenta.ru/rss/top7',
            'http://wsrss.bbc.co.uk/russian/index.xml']

    def get_rss(self, rss_url):
        http_client = AsyncHTTPClient()
        return http_client.fetch(rss_url, method='GET')

    def open(self):
        print("WebSocket opened")

        # Subject одновременно и observable, и observer
        self.subject = Subject()

        def send_response(x):
            self.write_message(json.dumps(x))

        def on_error(ex):
            print(ex)

        user_input = self.subject.throttle_last(
            1000  # На заданном временном промежутке получать последнее значение
        ).start_with(
            ''  # Сразу же после подписки отправляет значение по умолчанию
        ).filter(
            lambda text: not text or len(text) > 2
        )

        interval_obs = Observable.interval(
            60000  # Отдает значение раз в 60с (для периодического обновления)
        ).start_with(0)

        # combine_latest собирает 2 потока из запросов пользователя и временных
        # интервалов, срабатывает на любое сообщение из каждого потока
        self.combine_latest_sbs = user_input.combine_latest(
            interval_obs, lambda input_val, i: input_val
        ).do_action(  # Срабатывает на каждый выпущенный элемент
            # Отправляет сообщение для очистки списка на фронтэнд
            lambda x: send_response('clear')
        ).flat_map(
            # В цепочку встраивается observable для получения списка
            self.get_data
        ).subscribe(send_response, on_error)
        # Создается подписка; вся цепочка начинает работать только в этот момент

    def get_data(self, query):
        # Observable создается из списка url
        return Observable.from_list(
            self.urls
        ).flat_map(
            # Для каждого url создается observable, который загружает данные
            lambda url: Observable.from_future(self.get_rss(url))
        ).flat_map(
            # Полученные данные парсятся, из них создается observable
            lambda x: Observable.from_list(
                feedparser.parse(x.body)['entries']
            ).filter(
                # Фильтрует по вхождению запроса в заголовок или текст новости
                lambda val, i: query in val.title or query in val.summary
            ).take(5)  # Берем только по 5 новостей по каждому url
        ).map(lambda x: {'title': x.title, 'link': x.link,
                         'published': x.published, 'summary': x.summary})
        # Преобразует данные для отправки на фронтэнд

    def on_message(self, message):
        obj = json_decode(message)
        # Отправляет сообщение, который получает user_input
        self.subject.on_next(obj['term'])

    def on_close(self):
        # Отписаться от observable; по цепочке остановит работу всех observable
        self.combine_latest_sbs.dispose()
        print("WebSocket closed")


class MainHandler(RequestHandler):
    def get(self):
        self.render("index.html")


def main():
    AsyncIOMainLoop().install()

    port = os.environ.get("PORT", 8080)
    app = Application([
        url(r"/", MainHandler),
        (r'/ws', WSHandler),
        (r'/static/(.*)', StaticFileHandler, {'path': "."})
    ])
    print("Starting server at port: %s" % port)
    app.listen(port)
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()
