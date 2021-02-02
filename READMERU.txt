Проверка ссылки на фишинг с помощью PhishingKitHunter

Салам, бандиты. Перед вами скрипт, который значительно облегчит вашу жизнь в интернете. 

Обновим пакет:
apt update
apt upgrade

Качаем питон и гит:
apt install python
apt install git

Теперь копируем реп:
git clone https://github.com/t4d/PhishingKitHunter.git

И открываем его:
cd PhishingKitHunter

Устанавливаем зависимости:
pip3 install -r requirements.txt

Вот такой командой запускаем:
python PhishingKitHunter.py -i logs.log -o report.csv -c conf/defaults.conf

Для просмотра результата используем cat:
cat  report.csv

Собюдайте безопасность в сети 