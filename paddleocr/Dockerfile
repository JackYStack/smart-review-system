FROM paddlepaddle/paddle:3.0.0

RUN python -m pip install --no-cache-dir "paddlex[ocr]==3.7.2" "paddleocr==3.7.0" \
    && paddlex --install serving

ENV PADDLEOCR_DEVICE=cpu

EXPOSE 8080

CMD ["sh", "-c", "exec paddlex --serve --pipeline PP-StructureV3 --host 0.0.0.0 --port 8080 --device ${PADDLEOCR_DEVICE}"]
