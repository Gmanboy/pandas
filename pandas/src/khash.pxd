from cpython cimport PyObject
from numpy cimport int64_t, int32_t, uint32_t, float64_t

cdef extern from "khash_python.h":
    ctypedef uint32_t khint_t
    ctypedef khint_t khiter_t

    ctypedef struct kh_pymap_t:
        khint_t n_buckets, size, n_occupied, upper_bound
        uint32_t *flags
        PyObject **keys
        size_t *vals

    inline kh_pymap_t* kh_init_pymap()
    inline void kh_destroy_pymap(kh_pymap_t*)
    inline void kh_clear_pymap(kh_pymap_t*)
    inline khint_t kh_get_pymap(kh_pymap_t*, PyObject*)
    inline void kh_resize_pymap(kh_pymap_t*, khint_t)
    inline khint_t kh_put_pymap(kh_pymap_t*, PyObject*, int*)
    inline void kh_del_pymap(kh_pymap_t*, khint_t)

    bint kh_exist_pymap(kh_pymap_t*, khiter_t)

    ctypedef struct kh_pyset_t:
        khint_t n_buckets, size, n_occupied, upper_bound
        uint32_t *flags
        PyObject **keys
        size_t *vals

    inline kh_pyset_t* kh_init_pyset()
    inline void kh_destroy_pyset(kh_pyset_t*)
    inline void kh_clear_pyset(kh_pyset_t*)
    inline khint_t kh_get_pyset(kh_pyset_t*, PyObject*)
    inline void kh_resize_pyset(kh_pyset_t*, khint_t)
    inline khint_t kh_put_pyset(kh_pyset_t*, PyObject*, int*)
    inline void kh_del_pyset(kh_pyset_t*, khint_t)

    bint kh_exist_pyset(kh_pyset_t*, khiter_t)

    ctypedef char* kh_cstr_t

    ctypedef struct kh_str_t:
        khint_t n_buckets, size, n_occupied, upper_bound
        uint32_t *flags
        kh_cstr_t *keys
        size_t *vals

    inline kh_str_t* kh_init_str() nogil
    inline void kh_destroy_str(kh_str_t*) nogil
    inline void kh_clear_str(kh_str_t*) nogil
    inline khint_t kh_get_str(kh_str_t*, kh_cstr_t) nogil
    inline void kh_resize_str(kh_str_t*, khint_t) nogil
    inline khint_t kh_put_str(kh_str_t*, kh_cstr_t, int*) nogil
    inline void kh_del_str(kh_str_t*, khint_t) nogil

    bint kh_exist_str(kh_str_t*, khiter_t) nogil


    ctypedef struct kh_int64_t:
        khint_t n_buckets, size, n_occupied, upper_bound
        uint32_t *flags
        int64_t *keys
        size_t *vals

    inline kh_int64_t* kh_init_int64() nogil
    inline void kh_destroy_int64(kh_int64_t*) nogil
    inline void kh_clear_int64(kh_int64_t*) nogil
    inline khint_t kh_get_int64(kh_int64_t*, int64_t) nogil
    inline void kh_resize_int64(kh_int64_t*, khint_t) nogil
    inline khint_t kh_put_int64(kh_int64_t*, int64_t, int*) nogil
    inline void kh_del_int64(kh_int64_t*, khint_t) nogil

    bint kh_exist_int64(kh_int64_t*, khiter_t) nogil

    ctypedef struct kh_float64_t:
        khint_t n_buckets, size, n_occupied, upper_bound
        uint32_t *flags
        float64_t *keys
        size_t *vals

    inline kh_float64_t* kh_init_float64() nogil
    inline void kh_destroy_float64(kh_float64_t*) nogil
    inline void kh_clear_float64(kh_float64_t*) nogil
    inline khint_t kh_get_float64(kh_float64_t*, float64_t) nogil
    inline void kh_resize_float64(kh_float64_t*, khint_t) nogil
    inline khint_t kh_put_float64(kh_float64_t*, float64_t, int*) nogil
    inline void kh_del_float64(kh_float64_t*, khint_t) nogil

    bint kh_exist_float64(kh_float64_t*, khiter_t) nogil

    ctypedef struct kh_int32_t:
        khint_t n_buckets, size, n_occupied, upper_bound
        uint32_t *flags
        int32_t *keys
        size_t *vals

    inline kh_int32_t* kh_init_int32() nogil
    inline void kh_destroy_int32(kh_int32_t*) nogil
    inline void kh_clear_int32(kh_int32_t*) nogil
    inline khint_t kh_get_int32(kh_int32_t*, int32_t) nogil
    inline void kh_resize_int32(kh_int32_t*, khint_t) nogil
    inline khint_t kh_put_int32(kh_int32_t*, int32_t, int*) nogil
    inline void kh_del_int32(kh_int32_t*, khint_t) nogil

    bint kh_exist_int32(kh_int32_t*, khiter_t) nogil

    # sweep factorize

    ctypedef struct kh_strbox_t:
        khint_t n_buckets, size, n_occupied, upper_bound
        uint32_t *flags
        kh_cstr_t *keys
        PyObject **vals

    inline kh_strbox_t* kh_init_strbox() nogil
    inline void kh_destroy_strbox(kh_strbox_t*) nogil
    inline void kh_clear_strbox(kh_strbox_t*) nogil
    inline khint_t kh_get_strbox(kh_strbox_t*, kh_cstr_t) nogil
    inline void kh_resize_strbox(kh_strbox_t*, khint_t) nogil
    inline khint_t kh_put_strbox(kh_strbox_t*, kh_cstr_t, int*) nogil
    inline void kh_del_strbox(kh_strbox_t*, khint_t) nogil

    bint kh_exist_strbox(kh_strbox_t*, khiter_t) nogil
