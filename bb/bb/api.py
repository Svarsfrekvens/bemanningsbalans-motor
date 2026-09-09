"""Same-origin local API, or a token-protected service behind a company gateway.

Do not expose local mode to a network. There is no identity/durable database here.
"""
import asyncio
import json
import os
import secrets
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from .domain import check_input
from .validate import validate

app=FastAPI(title='Bemanningsbalans optimeringsmotor',version='1.0.0')
gate=asyncio.Lock()
MAX_BODY=6*1024*1024

allowed_origins=[x.strip() for x in os.environ.get('BB_ALLOWED_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=['GET','POST'],
    allow_headers=['Authorization','Content-Type'],
)


@app.middleware('http')
async def protect(request:Request,call_next):
    from fastapi.responses import JSONResponse
    token=os.environ.get('BB_API_TOKEN','')
    if request.url.path.startswith('/api/'):
        if token:
            supplied=request.headers.get('authorization','')
            if not secrets.compare_digest(supplied,'Bearer '+token):
                return JSONResponse({'detail':'Åtkomst nekad.'},status_code=401)
        elif not request.client or request.client.host not in ('127.0.0.1','::1','testclient'):
            return JSONResponse({'detail':'Lokal tjänst får bara användas från samma dator.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store'
    return response


async def payload(request):
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>MAX_BODY: raise HTTPException(413,'För stort underlag.')
    try:
        body=json.loads(content)
        check_input(body['data'])
        return body
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,str(exc)) from exc


@app.get('/api/health')
async def health():
    import importlib.util
    return dict(ready=importlib.util.find_spec('ortools') is not None,storage='session-and-excel')


@app.post('/api/validate')
async def validate_endpoint(request:Request):
    body=await payload(request)
    return validate(body['data'],body.get('schedule',body['data']['current']))


@app.post('/api/optimize')
async def optimize(request:Request):
    body=await payload(request)
    if gate.locked(): raise HTTPException(429,'En beräkning pågår. Försök igen när den är klar.')
    try:
        from .solver import solve
        async with gate:
            return await asyncio.to_thread(solve,body['data'],body.get('seconds',30))
    except ImportError as exc:
        raise HTTPException(503,'OR-Tools är inte installerat. Följ startinstruktionerna.') from exc
    except (ValueError,TypeError,OverflowError) as exc:
        raise HTTPException(422,str(exc)) from exc


@app.get('/')
async def index():
    return {'service':'Bemanningsbalans optimeringsmotor','status':'ok','health':'/api/health','docs':'/docs'}
