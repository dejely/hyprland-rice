// Qt-specific glue: release unused QML components after transient views close.
#include <QtQml/QQmlEngine>
#include <QtQml/QQmlExtensionPlugin>
#include <QtQml/qqml.h>
#include <QtGui/QGuiApplication>
#include <QtGui/QPixmapCache>
#include <QtQuick/QQuickWindow>
#ifdef __GLIBC__
#include <malloc.h>
#endif
class RiceMemory final : public QObject {
    Q_OBJECT
    QQmlEngine *engine;
public:
    explicit RiceMemory(QQmlEngine *e) : QObject(e), engine(e) {}
    Q_INVOKABLE void trim() {
        for (auto *window : QGuiApplication::allWindows()) {
            if (auto *quick = qobject_cast<QQuickWindow *>(window); quick && !quick->isVisible()) {
                quick->setPersistentGraphics(false);
                quick->setPersistentSceneGraph(false);
                quick->releaseResources();
            }
        }
        QPixmapCache::clear();
        engine->collectGarbage();
        // Keep Quickshell singleton type identities stable across view recreation.
#ifdef __GLIBC__
        malloc_trim(0);
#endif
    }
};
class RiceMemoryPlugin final : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override {
        qmlRegisterSingletonType<RiceMemory>(uri, 1, 0, "Memory",
            [](QQmlEngine *engine, QJSEngine *) -> QObject * {
                return new RiceMemory(engine);
            });
    }
};
#include "memory.moc"

