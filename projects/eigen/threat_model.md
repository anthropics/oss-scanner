# Eigen: threat model and severity guide for the scanner

Eigen (https://gitlab.com/libeigen/eigen, MPL-2.0) is a header-only C++14 template library for linear algebra:
dense and sparse matrices and arrays, decompositions, solvers and geometry under `Eigen/`, plus Tensor, FFT,
special functions, autodiff and other modules under `contrib/Eigen/`. TensorFlow depends on Tensor.
`/src/AGENTS.md` and the guides under `/src/.agents/` describe the code's conventions and hazards; read them first.

## What Eigen does and where untrusted input enters

Eigen is a library: the application decides what reaches it. "Untrusted" means data that an application can take
from a file or a remote party and pass to a public API having checked only the API's documented preconditions. The
entry points, roughly in order of exposure:

- **Matrix Market files** (`contrib/Eigen/src/SparseExtra/MarketIO.h`, via `<unsupported/Eigen/SparseExtra>`):
  `getMarketHeader`, `loadMarket`, `loadMarketDense`, `loadMarketVector`. Every byte of the file, including the
  banner, dimensions, entry count and indices, is attacker-controlled. Unlike a caller's arguments, the file is not
  a precondition: these functions must validate what they read before indexing or allocating with it.
- **Deserialization** (`Eigen/src/Core/util/Serializer.h`, in `Eigen/Core`): `Eigen::deserialize(src, end, ...)`
  and `Serializer<T>::deserialize`. Sizes stored in the buffer are attacker-controlled; the contract is that a short
  or inconsistent buffer yields `nullptr`, never an access outside `[src, end)`.
- **The BLAS and LAPACK libraries** (`blas/`, `lapack/`; `libeigen_blas*`, `libeigen_lapack*`): Fortran-ABI entry
  points such as `dgemm_` and `dgetrf_`. Arguments that the reference BLAS/LAPACK argument checks reject must be
  reported through `xerbla_` or `INFO < 0`. Arguments that pass those checks must keep every access inside the
  extents the reference interface defines (`n`, `lda`, `incx`, ...). The pointers themselves are the caller's promise.
- **Sizes computed from data**: `resize`, `conservativeResize`, the sizing constructors, `reserve`, `Map` and `Ref`
  extents, sparse `insert` and `setFromTriplets`, `reshaped`, indexed views. `rows * cols` and every size derived from
  it must not overflow into an undersized allocation; Eigen checks this and throws `std::bad_alloc`.
- **Values**: NaN, ±Inf, subnormals and extreme magnitudes are valid entries everywhere. A decomposition or solver may
  return a meaningless result or report failure through `info()`, but must not index out of bounds, loop forever or
  invoke UB. Pivot or index selection driven by comparisons with NaN is a known hazard class.
- **Threading**: `Eigen/ThreadPool` (`NonBlockingThreadPool`, `EventCount`, `RunQueue`, `Barrier`, `ForkJoin`),
  multithreaded GEMM (`setNbThreads`, OpenMP), and Tensor's `ThreadPoolDevice` executors: data races, lost wakeups,
  deadlocks, and use-after-free during shutdown.
- **External backends** (`Eigen/CholmodSupport`, `UmfPackSupport`, `KLUSupport`, `SPQRSupport`, `SuperLUSupport`,
  `PardisoSupport`, `PaStiXSupport`, `MetisSupport`): Eigen's glue, such as index-type narrowing and buffer sizing, is
  in scope. Bugs inside the third-party libraries are not ours.

The public API is the umbrella headers under `Eigen/` and `contrib/Eigen/` (also reachable as `unsupported/Eigen/`)
and what they export. Files under `Eigen/src/` and `contrib/Eigen/src/`, and everything in `namespace internal`, are
implementation: calling them directly with arguments that violate their asserted preconditions is not a bug.

## What matters most, and what is out of scope

Most important: memory safety in `Eigen/Core`, which covers allocation and size arithmetic, resizing, `Map`/`Ref`,
block and indexing expressions, and the packing and blocking of products at edge sizes and strides. Next come the
packet math under `Eigen/src/Core/arch/` (tail handling, partial loads and stores at the ends of arrays,
alignment), Sparse (storage, insertion, `setFromTriplets`, pruning, conversions), and the parsers and libraries above.

In scope at a lower priority: decompositions and solvers fed adversarial values, the `contrib/` modules (Tensor
first), and the backend glue.

Out of scope, so do not report:

- Numerical accuracy: results that are inaccurate or wrong but memory-safe, and non-convergence that `info()` reports.
- Caller precondition violations: indices or sizes that `eigen_assert` checks (debug builds check the contract;
  `NDEBUG` builds skip the check by design), mismatched dimensions, a `Map`/`Ref` over a buffer smaller than its
  declared extent or misaligned for its `Aligned` option, `.noalias()` on an aliased expression, a lazy expression kept
  in `auto` past its operands' lifetime, and concurrent writes to one object.
- An `eigen_assert` failure or abort for such a violation; that is the intended debug behavior.
- Cost proportional to a size the caller chose (a 10^5 × 10^5 dense matrix needs 80 GB).
- GPU code paths (CUDA, HIP, SYCL, `contrib/Eigen/GPU`); the scanner has no GPU.
- `lapack/*.f`: vendored netlib reference LAPACK. Problems there belong to Reference-LAPACK upstream.
- `test/`, `contrib/test/`, `benchmarks/`, `demos/`, `doc/`, `ci/` and `scripts/`: none of these ship to users.

## How to exercise it

`/src/build` is configured with clang-19, ASan and UBSan (`-fno-sanitize-recover=undefined`). Prebuilt: the BLAS and
LAPACK libraries, and the tests `serializer sizeoverflow dynalloc io zerosized indexed_view stl_iterators
sparse_basic sparse_extra tensor_io threads_*`. Other tests build offline with
`cmake --build /src/build --target <test>`; a test takes `s<seed>` and `r<repeats>` arguments. CTest names the parts
of a split test `<test>_<N>`.

For a standalone driver, include umbrella headers only:

```
clang++-19 -std=c++14 -I/src -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=undefined driver.cpp
```

The packet-math paths differ by ISA: build the same driver with `-march=x86-64-v3` (AVX2 and FMA), with
`-DEIGEN_DONT_VECTORIZE`, and with the default SSE2, and use sizes that are not multiples of the packet size. Run the
AVX-512 paths only if `/proc/cpuinfo` lists `avx512f`. `-DEIGEN_DEFAULT_TO_ROW_MAJOR` switches the default storage
order. Without `-DNDEBUG` the `eigen_assert` checks are on; use that to tell a precondition violation from a bug.

## How we rate severity

- **Critical**: a controllable out-of-bounds write or use-after-free reachable from file or buffer contents alone
  (`loadMarket*`, `deserialize`).
- **High**: an out-of-bounds write, use-after-free or double free in a public API called within its documented
  preconditions; an overflow in a size computation that yields an undersized allocation; an out-of-bounds read that
  discloses memory.
- **Medium**: an out-of-bounds read without disclosure, a null dereference, or UB with a demonstrated crash or
  miscompile; a data race, lost wakeup or deadlock in the thread pool under supported use; an infinite loop on finite
  input.
- **Low**: non-termination on NaN or Inf input; an allocation sized by an untrusted header before the data justifies
  it; UB without a demonstrated effect.

## Reports and patches

A reproducer is one `.cpp` file that includes only umbrella headers, with the exact compile command and the
sanitizer output. Write patches against `master` as C++14, formatted with the repository's `.clang-format`
(clang-format 17). Each patch adds a regression test to the nearest existing file under `test/` or `contrib/test/`,
using that file's `VERIFY` style.
