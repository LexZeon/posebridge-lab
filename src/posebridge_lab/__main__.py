if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    from .gpu_runtime import activate_local_runtime
    activate_local_runtime()
    from .app import main
    main()
