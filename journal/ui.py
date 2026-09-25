"""Shared list navigation, preserving selected filters."""
from flask import request, url_for


def query_url(**changes):
    values=request.args.to_dict()
    if 'page' in changes: values.pop('focus_task',None)
    values.update(changes)
    values.update(request.view_args or {})
    return url_for(request.endpoint, **{key:value for key,value in values.items() if value is not None})


def page_items(data, size=30, focus=None):
    total=len(data)
    pages=max(1,(total+size-1)//size)
    page=min(pages,max(1,request.args.get('page',1,type=int)))
    if focus is not None:
        match=next((i for i,item in enumerate(data) if item['id']==focus),None)
        if match is not None: page=match//size+1
    return data[(page-1)*size:page*size],dict(total=total,page=page,pages=pages)
