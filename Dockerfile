FROM python:3.13-slim

# Build dependencies for liboqs
RUN apt-get update && apt-get install -y \
    build-essential cmake git libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Compile liboqs from source (shared library required by liboqs-python)
RUN git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git /tmp/liboqs \
    && cmake -B /tmp/liboqs/build -S /tmp/liboqs \
       -DCMAKE_BUILD_TYPE=Release \
       -DBUILD_SHARED_LIBS=ON \
       -DCMAKE_INSTALL_PREFIX=/usr/local \
    && cmake --build /tmp/liboqs/build --parallel $(nproc) \
    && cmake --install /tmp/liboqs/build \
    && rm -rf /tmp/liboqs

ENV LD_LIBRARY_PATH=/usr/local/lib

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
