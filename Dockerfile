FROM pkgxdev/pkgx:latest
RUN mkdir /app
COPY ./* /app/
RUN cd /app
RUN dev 
RUN python3 -m pip install -r requirements.txt
RUN python3 bot.py