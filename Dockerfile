FROM pkgxdev/pkgx:latest
RUN mkdir /app/run
COPY * /app/run
RUN dev 
RUN cd /app/run
RUN python -m pip install -r requirements.txt
RUN python bot.py