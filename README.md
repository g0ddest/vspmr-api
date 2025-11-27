# vspmr-api
Парсинг сайта Верховного Совета ПМР http://www.vspmr.org и получение информации о законопроектах и чтениях.

Помимо установки python 3, mongodb, зависимостей `pip install -r requirements.txt` надо добавить в папку lib в проекте [doctotext](http://silvercoders.com/en/products/doctotext/) — достаточно просто распаковать.

В mongodb создать базу vspmr с коллекциями `event`, `file`, `initiation`, `initiation_entry`.
